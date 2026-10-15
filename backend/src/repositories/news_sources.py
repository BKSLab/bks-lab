"""Synchronize verified source profiles and persist collection preferences."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select, text, update
from sqlalchemy.orm import selectinload

from src.db.models.news_catalog import NewsCategory, NewsTopic
from src.core.news_slugs import SOURCE_SLUG_MAX, readable_slug
from src.core.news_source_schedule import (
    DEFAULT_SOURCE_SCHEDULE,
    SOURCE_SCHEDULE_LOCK,
    next_scheduled_check,
    validate_source_schedule,
)
from src.db.models.news_jobs import NewsJob
from src.db.models.news_sources import NewsSource
from src.exceptions.news import NewsConflictError
from src.repositories.news_base import NewsRepository


class NewsSourceRepository(NewsRepository):
    async def get_by_slug(self, slug: str) -> NewsSource | None:
        """Resolve a stable source address without interpreting numeric IDs."""
        async with self.operation():
            return await self.db_session.scalar(self.query().where(NewsSource.slug == slug))

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
            statement = self.query().where(NewsSource.profile_id.is_not(None)).order_by(NewsSource.priority.desc(), NewsSource.id)
            if active_only:
                statement = statement.where(NewsSource.active.is_(True))
            return list((await self.db_session.scalars(statement)).all())

    async def list_active(self) -> list[NewsSource]:
        """Return sources eligible for automatic collection."""
        return await self.list(active_only=True)

    async def list_collection_targets(self, source_ids: list[int]) -> list[NewsSource]:
        """Resolve an immutable manual collection scope without rereading enablement."""
        if not source_ids:
            return []
        async with self.operation():
            return list(await self.db_session.scalars(
                self.query().where(NewsSource.id.in_(source_ids), NewsSource.profile_id.is_not(None))
                .order_by(NewsSource.priority.desc(), NewsSource.id)
            ))

    async def synchronize_profiles(self, values: list[dict]) -> list[NewsSource]:
        """Sync verified metadata, retaining existing preferences, identities and history.

        Args:
            values: Trusted code-owned profiles, with their default calendars.

        Returns:
            Registered source rows in profile order; new rows are always paused.
        """
        async with self.operation():
            await self.db_session.execute(
                text("SELECT pg_advisory_xact_lock(:key)"), {"key": SOURCE_SCHEDULE_LOCK}
            )
            await self.db_session.execute(
                text("SELECT pg_advisory_xact_lock(:key)"), {"key": 721409083}
            )
            rows = list(await self.db_session.scalars(self.query().order_by(NewsSource.id).with_for_update()))
            identities = {entry["profile_id"] for entry in values}
            removed = [row.id for row in rows if row.profile_id and row.profile_id not in identities]
            for row in rows:
                if row.id in removed:
                    row.profile_id, row.next_check_at = None, None
            if removed:
                await self._cancel_scheduled(removed)
            result: list[NewsSource] = []
            metadata = {"profile_id", "name", "description", "url", "kind", "config", "priority", "trust_score", "vendor_affiliated"}
            now = datetime.now(timezone.utc)
            for entry in values:
                row = next((item for item in rows if item.profile_id == entry["profile_id"]), None)
                if row is None:
                    row = next((item for item in rows if item.profile_id is None and item.url == entry["url"]), None)
                if row is None:
                    base = entry["slug"]
                    slug, suffix = base, 1
                    while any(item.slug == slug for item in rows):
                        suffix += 1
                        tail = f"-{suffix}"
                        slug = f"{base[:SOURCE_SLUG_MAX - len(tail)].rstrip('-')}{tail}"
                    row = NewsSource(
                        slug=slug, active=False, topics=[], categories=[],
                        schedule=validate_source_schedule(entry.get("schedule", DEFAULT_SOURCE_SCHEDULE)).model_dump(mode="json"),
                    )
                    self.db_session.add(row)
                    rows.append(row)
                elif any(key in entry and entry[key] != getattr(row, key) for key in ("url", "kind", "config")):
                    row.etag, row.last_modified = None, None
                    row.cursor = {
                        key: value for key, value in (row.cursor or {}).items()
                        if key not in {"collection_version", "profile_version"}
                    }
                for key in metadata:
                    if key in entry:
                        setattr(row, key, entry[key])
                row.schedule = validate_source_schedule(row.schedule).model_dump(mode="json")
                if row.active and row.next_check_at is None:
                    row.next_check_at = next_scheduled_check(row.schedule, now)
                elif not row.active:
                    row.next_check_at = None
                result.append(row)
            await self.db_session.commit()
            return result

    async def _cancel_scheduled(self, source_ids: list[int]) -> None:
        await self.db_session.execute(
            update(NewsJob).where(
                NewsJob.source_id.in_(source_ids), NewsJob.status == "queued",
                NewsJob.payload.has_key("scheduled_slot"),
            ).values(status="cancelled", completed_at=func.now(), error="Source calendar or enablement changed")
        )

    async def update_preferences(
        self, source_id: int, values: dict, *, now: datetime | None = None,
    ) -> NewsSource | None:
        """Atomically replace source preferences and invalidate obsolete queued starts."""
        if set(values) - {"active", "schedule"}:
            raise ValueError("Only source enablement and calendar can be edited")
        async with self.operation():
            await self.db_session.execute(
                text("SELECT pg_advisory_xact_lock(:key)"), {"key": SOURCE_SCHEDULE_LOCK}
            )
            row = await self.db_session.scalar(
                self.query().where(NewsSource.id == source_id, NewsSource.profile_id.is_not(None))
                .with_for_update().execution_options(populate_existing=True)
            )
            if row is None:
                return None
            changed = any(getattr(row, key) != value for key, value in values.items())
            if changed:
                await self._assign(row, values)
                row.schedule = validate_source_schedule(row.schedule).model_dump(mode="json")
                row.next_check_at = next_scheduled_check(row.schedule, now or datetime.now(timezone.utc)) if row.active else None
                await self._cancel_scheduled([row.id])
            await self.db_session.commit()
            return row

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
            await self.db_session.execute(
                text("SELECT pg_advisory_xact_lock(:key)"), {"key": 721409083}
            )
            base = readable_slug(values["name"])
            if base in {"new", "catalogue", "discover"}:
                base = f"source-{base}"
            slug, suffix = base, 1
            while await self.db_session.scalar(select(NewsSource.id).where(NewsSource.slug == slug)):
                suffix += 1
                tail = f"-{suffix}"
                slug = f"{base[:SOURCE_SLUG_MAX - len(tail)].rstrip('-')}{tail}"
            row = NewsSource(slug=slug, topics=[], categories=[])
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
