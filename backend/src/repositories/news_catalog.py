"""Editorial topics and categories."""

from __future__ import annotations

from typing import Literal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from src.db.models.news_catalog import NewsCategory, NewsTopic
from src.repositories.news_base import NewsRepository

CatalogKind = Literal["topics", "categories"]


class NewsCatalogRepository(NewsRepository):
    @staticmethod
    def model(kind: CatalogKind) -> type[NewsTopic] | type[NewsCategory]:
        return {"topics": NewsTopic, "categories": NewsCategory}[kind]

    async def list(
        self, kind: CatalogKind, active_only: bool = False
    ) -> list[NewsTopic | NewsCategory]:
        """Read the taxonomy, including inactive historical entries when requested."""
        async with self.operation():
            model = self.model(kind)
            statement = select(model).order_by(model.name, model.id)
            if active_only:
                statement = statement.where(model.active.is_(True))
            return list((await self.db_session.scalars(statement)).all())

    async def create(self, kind: CatalogKind, values: dict) -> NewsTopic | NewsCategory:
        """Create one named taxonomy entry."""
        async with self.operation():
            row = self.model(kind)(**values)
            self.db_session.add(row)
            await self.db_session.commit()
            return row

    async def update(
        self, kind: CatalogKind, row_id: int, values: dict
    ) -> NewsTopic | NewsCategory | None:
        """Change labels without deleting the history that references them."""
        async with self.operation():
            row = await self.db_session.get(
                self.model(kind), row_id, with_for_update=True
            )
            if row is None:
                return None
            for key, value in values.items():
                setattr(row, key, value)
            await self.db_session.commit()
            return row

    async def seed(self, kind: CatalogKind, entries: list[dict]) -> None:
        """Insert missing defaults without overwriting editorial customizations."""
        async with self.operation():
            for entry in entries:
                await self.db_session.execute(
                    insert(self.model(kind))
                    .values(**entry)
                    .on_conflict_do_nothing(index_elements=["name"])
                )
            await self.db_session.commit()
