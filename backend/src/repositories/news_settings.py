"""Database overrides for runtime editorial settings."""

from datetime import datetime, timezone

from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert

from src.db.models.news_settings import NewsSetting
from src.db.models.news_sources import NewsSource
from src.db.models.news_jobs import NewsJob
from src.core.news_source_schedule import SOURCE_SCHEDULE_LOCK, next_scheduled_check
from src.repositories.news_base import NewsRepository


class NewsSettingsRepository(NewsRepository):
    async def get(self) -> dict:
        """Return saved overrides; defaults are composed by the service."""
        async with self.operation():
            row = await self.db_session.get(NewsSetting, 1)
            return dict(row.value) if row else {}

    async def set(self, values: dict, *, now: datetime | None = None) -> dict:
        """Merge settings under a row lock to avoid lost concurrent patches."""
        async with self.operation():
            await self.db_session.execute(
                text("SELECT pg_advisory_xact_lock(:key)"), {"key": SOURCE_SCHEDULE_LOCK}
            )
            await self.db_session.execute(
                insert(NewsSetting).values(id=1, value={}).on_conflict_do_nothing()
            )
            row = await self.db_session.scalar(
                select(NewsSetting).where(NewsSetting.id == 1).with_for_update()
            )
            if "enabled" in values and values["enabled"] != row.value.get("enabled", True):
                now = now or datetime.now(timezone.utc)
                sources = list(await self.db_session.scalars(
                    select(NewsSource).where(NewsSource.profile_id.is_not(None), NewsSource.active.is_(True))
                    .with_for_update()
                ))
                for source in sources:
                    source.next_check_at = next_scheduled_check(source.schedule, now)
                await self.db_session.execute(
                    update(NewsJob).where(NewsJob.status == "queued", NewsJob.payload.has_key("scheduled_slot"))
                    .values(status="cancelled", completed_at=func.now(), error="Automatic collection pause changed")
                )
            row.value = {**row.value, **values}
            await self.db_session.commit()
            return dict(row.value)
