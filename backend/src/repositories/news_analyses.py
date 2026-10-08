"""Idempotent analysis persistence fenced by content version and job ownership."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload

from src.db.models import NewsAnalysis, NewsItem, NewsTopic
from src.repositories.news_base import NewsRepository


class NewsAnalysisRepository(NewsRepository):
    @staticmethod
    def query():
        return select(NewsAnalysis).options(
            joinedload(NewsAnalysis.category), selectinload(NewsAnalysis.topics)
        )

    async def list_for_item(self, item_id: int) -> list[NewsAnalysis]:
        """Read distinct content/model/prompt outputs, newest analysis first."""
        async with self.operation():
            return list(
                (
                    await self.db_session.scalars(
                        self.query()
                        .where(NewsAnalysis.item_id == item_id)
                        .order_by(
                            NewsAnalysis.created_at.desc(), NewsAnalysis.id.desc()
                        )
                    )
                ).all()
            )

    async def save(
        self,
        item_id: int,
        content_hash: str,
        model: str,
        prompt_version: str,
        data: dict,
        *,
        job_id: int | None = None,
        owner_token: str | None = None,
        replace_existing: bool = False,
    ) -> NewsAnalysis | None:
        """Store one output; explicit reanalysis may refresh the same fenced identity."""
        async with self.operation():
            await self.fence(job_id, owner_token)
            item = await self.db_session.scalar(
                select(NewsItem)
                .where(NewsItem.id == item_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if item is None or item.content_hash != content_hash:
                await self.db_session.rollback()
                return None
            row = await self.db_session.scalar(
                self.query().where(
                    NewsAnalysis.item_id == item_id,
                    NewsAnalysis.content_hash == content_hash,
                    NewsAnalysis.model == model,
                    NewsAnalysis.prompt_version == prompt_version,
                )
            )
            if row is None or replace_existing:
                values = {
                    key: value
                    for key, value in data.items()
                    if key
                    in {
                        "is_relevant",
                        "category_id",
                        "suggested_topics",
                        "scores",
                        "summary_ru",
                        "editorial_comment_ru",
                        "recommended_formats",
                        "confidence",
                        "needs_verification",
                        "news_score",
                        "article_score",
                    }
                }
                topics = list(
                    (
                        await self.db_session.scalars(
                            select(NewsTopic).where(
                                NewsTopic.id.in_(data.get("topic_ids", []))
                            )
                        )
                    ).all()
                )
                if row is None:
                    row = NewsAnalysis(
                        item_id=item_id,
                        content_hash=content_hash,
                        model=model,
                        prompt_version=prompt_version,
                        **values,
                        topics=topics,
                    )
                    self.db_session.add(row)
                else:
                    for key, value in values.items():
                        setattr(row, key, value)
                    row.topics, row.created_at = topics, datetime.now(timezone.utc)
                await self.db_session.flush()
            item.latest_analysis_id, item.status = row.id, "analyzed"
            await self.db_session.commit()
            return await self.db_session.scalar(
                self.query()
                .where(NewsAnalysis.id == row.id)
                .execution_options(populate_existing=True)
            )
