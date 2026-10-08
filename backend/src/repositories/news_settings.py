"""Database overrides for runtime editorial settings."""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from src.db.models.news_settings import NewsSetting
from src.repositories.news_base import NewsRepository


class NewsSettingsRepository(NewsRepository):
    async def get(self) -> dict:
        """Return saved overrides; defaults are composed by the service."""
        async with self.operation():
            row = await self.db_session.get(NewsSetting, 1)
            return dict(row.value) if row else {}

    async def set(self, values: dict) -> dict:
        """Merge settings under a row lock to avoid lost concurrent patches."""
        async with self.operation():
            await self.db_session.execute(
                insert(NewsSetting).values(id=1, value={}).on_conflict_do_nothing()
            )
            row = await self.db_session.scalar(
                select(NewsSetting).where(NewsSetting.id == 1).with_for_update()
            )
            row.value = {**row.value, **values}
            await self.db_session.commit()
            return dict(row.value)
