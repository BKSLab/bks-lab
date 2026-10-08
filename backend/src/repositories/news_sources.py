"""Persist validated source configurations and explicit taxonomy assignments."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.db.models.news_catalog import NewsCategory, NewsTopic
from src.db.models.news_sources import NewsSource
from src.exceptions.news import NewsConflictError
from src.repositories.news_base import NewsRepository


class NewsSourceRepository(NewsRepository):
    @staticmethod
    def query():
        return select(NewsSource).options(
            selectinload(NewsSource.topics), selectinload(NewsSource.categories)
        )

    async def get(self, source_id: int) -> NewsSource | None:
        """Read a source and its taxonomy without lazy SQL."""
        async with self.operation():
            return await self.db_session.scalar(
                self.query().where(NewsSource.id == source_id)
            )

    async def list(self, active_only: bool = False) -> list[NewsSource]:
        """List sources by editorial priority and ID."""
        async with self.operation():
            statement = self.query().order_by(NewsSource.priority.desc(), NewsSource.id)
            if active_only:
                statement = statement.where(NewsSource.active.is_(True))
            return list((await self.db_session.scalars(statement)).all())

    async def list_active(self) -> list[NewsSource]:
        """Return sources eligible for automatic collection."""
        return await self.list(active_only=True)

    async def _assign(self, row: NewsSource, values: dict) -> None:
        for key, value in values.items():
            if key in {"topic_ids", "category_ids"}:
                model, attribute = (
                    (NewsTopic, "topics")
                    if key == "topic_ids"
                    else (NewsCategory, "categories")
                )
                entries = list(
                    (
                        await self.db_session.scalars(
                            select(model).where(model.id.in_(value))
                        )
                    ).all()
                )
                setattr(row, attribute, entries)
            else:
                setattr(row, key, value)

    async def create(self, values: dict) -> NewsSource:
        """Save one checked source and its editorial tags in one transaction."""
        async with self.operation():
            row = NewsSource(topics=[], categories=[])
            await self._assign(row, values)
            self.db_session.add(row)
            await self.db_session.commit()
            return row

    async def update(
        self, source_id: int, values: dict, *, expected: dict | None = None
    ) -> NewsSource | None:
        """Apply a checked source edit; reset cursors when adapter configuration changes."""
        async with self.operation():
            row = await self.db_session.scalar(
                self.query()
                .where(NewsSource.id == source_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if row is None:
                return None
            if expected is not None and any(
                getattr(row, key) != value for key, value in expected.items()
            ):
                raise NewsConflictError("Source changed during validation")
            if any(
                key in values and values[key] != getattr(row, key)
                for key in ("url", "kind", "config")
            ):
                row.cursor, row.etag, row.last_modified, row.last_success_at = (
                    {},
                    None,
                    None,
                    None,
                )
                row.health, row.last_error = "unknown", None
            await self._assign(row, values)
            await self.db_session.commit()
            return row

    async def mark_error(
        self,
        source_id: int,
        error: str,
        *,
        job_id: int | None = None,
        owner_token: str | None = None,
    ) -> None:
        """Store a safe fetch failure without moving the last successful cursor."""
        async with self.operation():
            await self.fence(job_id, owner_token)
            row = await self.db_session.get(NewsSource, source_id, with_for_update=True)
            if row is not None:
                row.last_error, row.health = error[:500], "error"
            await self.db_session.commit()
