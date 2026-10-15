"""Atomic ingestion, deduplication, retrieval and retention of collected material."""

from datetime import datetime, timezone

from sqlalchemy import and_, delete, exists, func, or_, select, text, update
from sqlalchemy.orm import joinedload

from src.db.models import (
    NewsAnalysis,
    NewsEditorialDecision,
    NewsItem,
    NewsJob,
    NewsRunItem,
    NewsSource,
    NewsSourceRun,
)
from src.db.models.news_catalog import news_analysis_topics
from src.exceptions.news import NewsConflictError, NewsSourceChangedError
from src.repositories.news_base import NewsRepository
from src.schemas.news_collection import NEWS_MIN_CONTENT_CHARS


class NewsItemRepository(NewsRepository):
    @staticmethod
    def _source_url_aliases(metadata: dict | None) -> set[str]:
        """Read normalized observation URLs retained by this repository."""
        aliases = (metadata or {}).get("source_url_aliases", [])
        return {url for url in aliases if isinstance(url, str)} if isinstance(aliases, list) else set()

    async def ids_for_source(self, source_id: int) -> list[int]:
        """Read retained identities for an explicitly requested repair."""
        async with self.operation():
            return list(await self.db_session.scalars(
                select(NewsItem.id).where(NewsItem.source_id == source_id).order_by(NewsItem.id)
            ))

    async def repair_batch(self, source_id: int, item_ids: list[int]) -> list[NewsItem]:
        """Read a bounded repair batch restricted to its owning source."""
        async with self.operation():
            return list(await self.db_session.scalars(
                self.query().where(NewsItem.source_id == source_id, NewsItem.id.in_(item_ids[:200]))
                .order_by(NewsItem.id)
            ))

    async def known_urls(self, source_id: int) -> set[str]:
        """Read identities that remain eligible for updates outside the initial import window."""
        async with self.operation():
            rows = await self.db_session.execute(
                select(NewsItem.url, NewsItem.normalized_url, NewsItem.metadata_json)
                .where(NewsItem.source_id == source_id)
            )
            return {
                url for original, canonical, metadata in rows
                for url in ({original, canonical} | self._source_url_aliases(metadata))
            }

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
                    or_(
                        NewsJob.dedupe_key == func.concat(
                            "analysis:", NewsItem.id, ":", NewsItem.content_hash,
                            ":", model, ":", prompt_version,
                        ),
                        and_(
                            NewsJob.status.in_(["queued", "running"]),
                            NewsJob.payload["content_hash"].astext == NewsItem.content_hash,
                        ),
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
                            func.greatest(func.length(NewsItem.content), func.length(NewsItem.excerpt))
                            >= NEWS_MIN_CONTENT_CHARS,
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
        collection_warning: str | None = None,
        run_id: int | None = None,
        skipped: list[dict] | None = None,
        run_diagnostics: dict | None = None,
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
            if run_id is not None:
                run = await self.db_session.get(NewsSourceRun, run_id, with_for_update=True)
                if run is None or run.source_id != source_id or run.job_id != job_id:
                    raise NewsConflictError("Collection report does not belong to this source and job")
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
                observation = dict(values.get("metadata_json") or {})
                preserved_previous = False
                # Source adapters normalize these URLs while retaining meaningful query fields.
                aliases = {values["url"]}
                identity_urls = {values["url"], values["normalized_url"]}
                identity = [
                    NewsItem.normalized_url.in_(identity_urls),
                    NewsItem.url.in_(identity_urls),
                    *(NewsItem.metadata_json["source_url_aliases"].contains([url]) for url in identity_urls),
                ]
                if values.get("external_id"):
                    identity.append(NewsItem.external_id == values["external_id"])
                existing_item_id = data.get("existing_item_id")
                if existing_item_id is not None:
                    identity.append(NewsItem.id == existing_item_id)
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
                if existing_item_id is not None and not any(row.id == existing_item_id for row in matches):
                    continue
                if len(matches) > 1:
                    raise NewsConflictError(
                        "Source identifiers refer to different stored items"
                    )
                row = matches[0] if matches else None
                if row is None:
                    values["metadata_json"] = {**values.get("metadata_json", {}), "source_url_aliases": sorted(aliases)}
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
                    outcome = "new"
                else:
                    aliases.add(row.url)
                    aliases.update(self._source_url_aliases(row.metadata_json))
                    incoming_metadata = values.get("metadata_json", {})
                    incoming_length = max(len(values.get("content", "")), len(values.get("excerpt", "")))
                    previous_length = max(len(row.content), len(row.excerpt))
                    degraded = previous_length >= NEWS_MIN_CONTENT_CHARS and (
                        incoming_length < NEWS_MIN_CONTENT_CHARS
                        or incoming_metadata.get("collection_status") == "fetch_failed"
                    )
                    if degraded:
                        preserved_previous = True
                        # A failed fetch is not an editorial revision. Preserve the last usable text.
                        for key in ("title", "excerpt", "content", "content_hash", "canonical_url", "normalized_url"):
                            values[key] = getattr(row, key)
                        values["metadata_json"] = {
                            **(row.metadata_json or {}),
                            "collection_status": "ready",
                            "collection_warning": "Не удалось обновить текст; сохранена предыдущая версия.",
                        }
                    values["metadata_json"] = {**values.get("metadata_json", {}), "source_url_aliases": sorted(aliases)}
                    changed = row.content_hash != values["content_hash"]
                    if row.external_id:
                        values.pop("external_id", None)
                    if not changed and existing_item_id is None:
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
                    outcome = "updated" if changed else "unchanged"
                counts["item_ids"].append(row.id)
                if run_id is not None:
                    warning = observation.get("collection_warning")
                    if not warning and max(len(data.get("content", "")), len(data.get("excerpt", ""))) < NEWS_MIN_CONTENT_CHARS:
                        warning = "Недостаточно текста для анализа."
                    self.db_session.add(NewsRunItem(
                        run_id=run_id, item_id=row.id,
                        title=data["title"][:1000], url=data["url"], outcome=outcome,
                        content_hash=row.content_hash,
                        warning=str(warning)[:500] if warning else None,
                        stage=observation.get("collection_stage") or ("extraction" if warning else None),
                        preserved_previous=preserved_previous,
                        reason="Такой материал уже найден в другом источнике." if row.duplicate_of_id else None,
                    ))
            if run_id is not None:
                self.db_session.add_all([
                    NewsRunItem(
                        run_id=run_id, item_id=None, title=str(entry.get("title") or "Без заголовка")[:1000],
                        url=entry.get("url"), outcome="skipped", reason=str(entry["reason"])[:500],
                        stage=entry.get("stage"), preserved_previous=False,
                    ) for entry in skipped or []
                ])
                diagnostics = run_diagnostics or {}
                run.status, run.completed_at = "completed", now
                run.new_count, run.updated_count, run.unchanged_count = (
                    counts["new"], counts["updated"], counts["unchanged"],
                )
                run.skipped_count = len(skipped or [])
                run.warning_count = diagnostics.get("warning_count", 0)
                run.http_status = diagnostics.get("http_status")
                run.not_modified = diagnostics.get("not_modified", False)
                run.limit_reached = diagnostics.get("limit_reached", False)
                run.diagnostics_truncated = diagnostics.get("diagnostics_truncated", False)
                run.error = collection_warning[:500] if collection_warning else None
            source.cursor, source.etag, source.last_modified = (
                cursor,
                etag,
                last_modified,
            )
            source.last_success_at, source.last_error, source.health = (
                now,
                collection_warning,
                "degraded" if collection_warning else "healthy",
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
