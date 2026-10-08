"""Atomic ingestion, deduplication, retrieval and retention of collected material."""

from datetime import datetime, timezone

from sqlalchemy import delete, exists, func, or_, select, text, update
from sqlalchemy.orm import joinedload

from src.db.models import (
    NewsAnalysis,
    NewsEditorialDecision,
    NewsItem,
    NewsJob,
    NewsSource,
    NewsSourceRun,
)
from src.db.models.news_catalog import news_analysis_topics
from src.exceptions.news import NewsConflictError, NewsSourceChangedError
from src.repositories.news_base import NewsRepository


class NewsItemRepository(NewsRepository):
    @staticmethod
    def query():
        return select(NewsItem).options(
            joinedload(NewsItem.source),
            joinedload(NewsItem.decision),
            joinedload(NewsItem.analysis).joinedload(NewsAnalysis.category),
            joinedload(NewsItem.analysis).selectinload(NewsAnalysis.topics),
        )

    async def get(self, item_id: int) -> NewsItem | None:
        """Read one current material and its explicit relations."""
        async with self.operation():
            return await self.db_session.scalar(
                self.query()
                .where(NewsItem.id == item_id)
                .execution_options(populate_existing=True)
            )

    async def list_page(
        self,
        *,
        page: int,
        page_size: int,
        source_id: int | None = None,
        category_id: int | None = None,
        topic_id: int | None = None,
        format: str | None = None,
        status: str | None = None,
        decision: str | None = None,
        min_score: float | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> tuple[list[NewsItem], int]:
        """Filter on the current analysis and latest decision, then paginate deterministically."""
        async with self.operation():
            statement = (
                self.query()
                .outerjoin(NewsAnalysis, NewsItem.latest_analysis_id == NewsAnalysis.id)
                .outerjoin(
                    NewsEditorialDecision,
                    NewsItem.latest_decision_id == NewsEditorialDecision.id,
                )
            )
            conditions = []
            if source_id is not None:
                conditions.append(NewsItem.source_id == source_id)
            if category_id is not None:
                conditions.append(NewsAnalysis.category_id == category_id)
            if topic_id is not None:
                conditions.append(
                    exists(
                        select(1).where(
                            news_analysis_topics.c.analysis_id == NewsAnalysis.id,
                            news_analysis_topics.c.topic_id == topic_id,
                        )
                    )
                )
            if format is not None:
                conditions.append(NewsAnalysis.recommended_formats.contains([format]))
            if status is not None:
                conditions.append(NewsItem.status == status)
            if decision is not None:
                conditions.append(NewsEditorialDecision.decision == decision)
            score = (
                NewsAnalysis.article_score
                if format == "longread_candidate"
                else NewsAnalysis.news_score
            )
            if min_score is not None:
                conditions.append(score >= min_score)
            if date_from is not None:
                conditions.append(NewsItem.first_seen_at >= date_from)
            if date_to is not None:
                conditions.append(NewsItem.first_seen_at <= date_to)
            statement = statement.where(*conditions)
            total = await self.db_session.scalar(
                select(func.count()).select_from(statement.subquery())
            )
            rows = list(
                (
                    await self.db_session.scalars(
                        statement.order_by(
                            score.desc().nullslast(),
                            NewsItem.first_seen_at.desc(),
                            NewsItem.id.desc(),
                        )
                        .offset((page - 1) * page_size)
                        .limit(page_size)
                    )
                ).all()
            )
            return rows, total or 0

    async def pending(
        self, limit: int, model: str | None = None, prompt_version: str | None = None
    ) -> list[NewsItem]:
        """Select pending nonduplicates not already attempted for the current analysis identity."""
        async with self.operation():
            jobs = select(NewsJob.id).where(
                NewsJob.kind == "analyze", NewsJob.item_id == NewsItem.id
            )
            if model is not None and prompt_version is not None:
                jobs = jobs.where(
                    NewsJob.dedupe_key
                    == func.concat(
                        "analysis:",
                        NewsItem.id,
                        ":",
                        NewsItem.content_hash,
                        ":",
                        model,
                        ":",
                        prompt_version,
                    )
                )
            else:
                jobs = jobs.where(NewsJob.status.in_(["queued", "running"]))
            return list(
                (
                    await self.db_session.scalars(
                        self.query()
                        .where(
                            NewsItem.status == "pending_analysis",
                            NewsItem.duplicate_of_id.is_(None),
                            or_(NewsItem.content != "", NewsItem.excerpt != ""),
                            ~exists(jobs),
                        )
                        .order_by(NewsItem.first_seen_at, NewsItem.id)
                        .limit(limit)
                    )
                ).all()
            )

    async def ingest(
        self,
        source_id: int,
        items: list[dict],
        cursor: dict,
        *,
        etag: str | None = None,
        last_modified: str | None = None,
        job_id: int | None = None,
        owner_token: str | None = None,
        expected_url: str | None = None,
        expected_kind: str | None = None,
        expected_config: dict | None = None,
    ) -> dict:
        """Commit observations and source cursor together after deduplication and ownership checks."""
        async with self.operation():
            await self.fence(job_id, owner_token)
            source = await self.db_session.scalar(
                select(NewsSource)
                .where(NewsSource.id == source_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if source is None or any(
                expected is not None and getattr(source, key) != expected
                for key, expected in (
                    ("url", expected_url),
                    ("kind", expected_kind),
                    ("config", expected_config),
                )
            ):
                raise NewsSourceChangedError("Source configuration changed")
            # Equal normalized URLs serialize across sources, making duplicate links deterministic.
            for url in sorted({item["normalized_url"] for item in items}):
                await self.db_session.execute(
                    text("SELECT pg_advisory_xact_lock(hashtextextended(:url, 0))"),
                    {"url": url},
                )
            counts = {"new": 0, "updated": 0, "unchanged": 0, "item_ids": []}
            now = datetime.now(timezone.utc)
            fields = {
                "external_id",
                "url",
                "canonical_url",
                "normalized_url",
                "title",
                "excerpt",
                "content",
                "content_hash",
                "metadata_json",
                "published_at",
                "updated_at",
            }
            for data in items:
                values = {key: value for key, value in data.items() if key in fields}
                identity = [NewsItem.normalized_url == values["normalized_url"]]
                if values.get("external_id"):
                    identity.append(NewsItem.external_id == values["external_id"])
                matches = list(
                    (
                        await self.db_session.scalars(
                            select(NewsItem)
                            .where(NewsItem.source_id == source_id, or_(*identity))
                            .order_by(NewsItem.id)
                            .with_for_update()
                        )
                    ).all()
                )
                if len(matches) > 1:
                    raise NewsConflictError(
                        "Source identifiers refer to different stored items"
                    )
                row = matches[0] if matches else None
                if row is None:
                    duplicate = await self.db_session.scalar(
                        select(NewsItem.id)
                        .where(
                            NewsItem.normalized_url == values["normalized_url"],
                            NewsItem.source_id != source_id,
                        )
                        .order_by(NewsItem.id)
                        .limit(1)
                    )
                    row = NewsItem(
                        source_id=source_id,
                        **values,
                        duplicate_of_id=duplicate,
                        first_seen_at=now,
                        last_seen_at=now,
                    )
                    self.db_session.add(row)
                    await self.db_session.flush()
                    counts["new"] += 1
                else:
                    changed = row.content_hash != values["content_hash"]
                    if row.external_id:
                        values.pop("external_id", None)
                    if not changed:
                        # Preserve text retention and the analysis when only metadata changes.
                        for key in ("title", "excerpt", "content", "content_hash"):
                            values.pop(key, None)
                    previous_url = row.normalized_url
                    for key, value in values.items():
                        setattr(row, key, value)
                    if previous_url != row.normalized_url:
                        row.duplicate_of_id = await self.db_session.scalar(
                            select(NewsItem.id)
                            .where(
                                NewsItem.normalized_url == row.normalized_url,
                                NewsItem.source_id != source_id,
                                NewsItem.id < row.id,
                            )
                            .order_by(NewsItem.id)
                            .limit(1)
                        )
                    if changed:
                        row.status, row.latest_analysis_id = "pending_analysis", None
                    row.last_seen_at = now
                    counts["updated" if changed else "unchanged"] += 1
                counts["item_ids"].append(row.id)
            source.cursor, source.etag, source.last_modified = (
                cursor,
                etag,
                last_modified,
            )
            source.last_success_at, source.last_error, source.health = (
                now,
                None,
                "healthy",
            )
            source.last_new_count = counts["new"]
            await self.db_session.commit()
            return counts

    async def retain(
        self, text_before: datetime, history_before: datetime
    ) -> dict[str, int]:
        """Remove expired text and old history while preserving current editorial output."""
        async with self.operation():
            counts = {}
            result = await self.db_session.execute(
                update(NewsItem)
                .where(
                    NewsItem.last_seen_at < text_before,
                    or_(NewsItem.content != "", NewsItem.excerpt != ""),
                )
                .values(content="", excerpt="")
            )
            counts["texts"] = result.rowcount
            current_analyses = select(NewsItem.latest_analysis_id).where(
                NewsItem.latest_analysis_id.is_not(None)
            )
            result = await self.db_session.execute(
                delete(NewsAnalysis).where(
                    NewsAnalysis.created_at < history_before,
                    NewsAnalysis.id.not_in(current_analyses),
                )
            )
            counts["analyses"] = result.rowcount
            current_decisions = select(NewsItem.latest_decision_id).where(
                NewsItem.latest_decision_id.is_not(None)
            )
            result = await self.db_session.execute(
                delete(NewsEditorialDecision).where(
                    NewsEditorialDecision.created_at < history_before,
                    NewsEditorialDecision.id.not_in(current_decisions),
                )
            )
            counts["decisions"] = result.rowcount
            result = await self.db_session.execute(
                delete(NewsSourceRun).where(
                    NewsSourceRun.completed_at < history_before,
                    NewsSourceRun.status != "running",
                )
            )
            counts["runs"] = result.rowcount
            result = await self.db_session.execute(
                delete(NewsJob).where(
                    NewsJob.completed_at < history_before,
                    NewsJob.status.in_(["completed", "failed", "cancelled"]),
                )
            )
            counts["jobs"] = result.rowcount
            await self.db_session.commit()
            return counts
