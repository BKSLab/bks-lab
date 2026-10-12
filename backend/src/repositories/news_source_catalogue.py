"""Read suggestions and insert missing seed rows without changing existing data."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from src.db.models.news_source_catalogue import NewsSourceCatalogueEntry
from src.repositories.news_base import NewsRepository


class NewsSourceCatalogueRepository(NewsRepository):
    async def list(self) -> list[NewsSourceCatalogueEntry]:
        """Read all catalogue suggestions in their preserved display order."""
        async with self.operation():
            statement = select(NewsSourceCatalogueEntry).order_by(
                NewsSourceCatalogueEntry.position, NewsSourceCatalogueEntry.id,
            )
            return list((await self.db_session.scalars(statement)).all())

    async def seed(self, entries: list[dict[str, Any]]) -> int:
        """Insert only missing IDs; a unique key also protects concurrent startups."""
        async with self.operation():
            existing = set(await self.db_session.scalars(select(NewsSourceCatalogueEntry.id)))
            missing = [entry for entry in entries if entry["id"] not in existing]
            if not missing:
                return 0
            statement = (
                insert(NewsSourceCatalogueEntry).values(missing)
                .on_conflict_do_nothing(index_elements=["id"])
                .returning(NewsSourceCatalogueEntry.id)
            )
            inserted = list((await self.db_session.scalars(statement)).all())
            await self.db_session.commit()
            return len(inserted)
