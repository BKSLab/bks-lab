"""PostgreSQL queue with atomic acquisition, ownership fencing and bounded retries."""

from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import joinedload

from src.core.news_slugs import JOB_SLUG_MAX, job_slug_base, readable_slug
from src.core.news_source_schedule import (
    SOURCE_SCHEDULE_LOCK, latest_scheduled_check, next_scheduled_check,
)
from src.db.models.news_jobs import NewsJob, NewsSourceRun
from src.db.models.news_items import NewsItem
from src.db.models.news_sources import NewsSource
from src.db.models.news_settings import NewsSetting
from src.repositories.news_base import NewsRepository

QUEUE_LOCK = 721409081
SCHEDULE_LOCK = SOURCE_SCHEDULE_LOCK
JOB_SLUG_LOCK = 721409084


class NewsJobRepository(NewsRepository):
    async def _new_slug(
        self, kind: str, *, source_id: int | None = None,
        item_id: int | None = None, payload: dict | None = None,
        created_at: datetime | None = None,
    ) -> str:
        await self.db_session.execute(
            text("SELECT pg_advisory_xact_lock(:key)"), {"key": JOB_SLUG_LOCK}
        )
        scope = "all-sources"
        if source_id is not None:
            scope = await self.db_session.scalar(select(NewsSource.slug).where(NewsSource.id == source_id)) or "source"
        elif item_id is not None:
            material = (await self.db_session.execute(
                select(NewsSource.slug, NewsItem.title).join(NewsItem, NewsItem.source_id == NewsSource.id).where(NewsItem.id == item_id)
            )).first()
            scope = f"{material[0]}-{readable_slug(material[1], fallback='material', limit=70)}" if material else "material"
        elif kind == "discover":
            scope = readable_slug(urlsplit((payload or {}).get("url", "")).hostname or "source")
        base = job_slug_base(kind, scope, created_at=created_at)
        slug, suffix = base, 1
        while await self.db_session.scalar(select(NewsJob.id).where(NewsJob.slug == slug)):
            suffix += 1
            tail = f"-{suffix}"
            stamp, prefix = base[-17:], base[:-18]
            scope_limit = JOB_SLUG_MAX - len(stamp) - len(tail) - 1
            slug = f"{prefix[:scope_limit].rstrip('-')}-{stamp}{tail}"
        return slug

    async def get_by_slug(self, slug: str) -> NewsJob | None:
        """Read queue state by its public address with source context loaded."""
        async with self.operation():
            return await self.db_session.scalar(
                select(NewsJob).where(NewsJob.slug == slug).options(
                    joinedload(NewsJob.source), joinedload(NewsJob.item).joinedload(NewsItem.source)
                )
            )

    async def enqueue_repair(
        self, source_id: int, item_ids: list[int], batch_size: int = 50,
    ) -> list[NewsJob]:
        """Atomically queue bounded repair batches, reusing an already active source repair."""
        if not item_ids:
            return []
        if not 1 <= batch_size <= 200:
            raise ValueError("Repair batch size must be between 1 and 200")
        async with self.operation():
            await self.db_session.execute(
                text("SELECT pg_advisory_xact_lock(:key)"), {"key": QUEUE_LOCK}
            )
            existing = list(await self.db_session.scalars(
                select(NewsJob).where(
                    NewsJob.kind == "collect", NewsJob.source_id == source_id,
                    NewsJob.status.in_(["queued", "running"]),
                    NewsJob.payload.has_key("repair_item_ids"),
                ).order_by(NewsJob.id)
            ))
            if existing:
                await self.db_session.commit()
                return existing
            ids = sorted(set(item_ids))
            rows = []
            for start in range(0, len(ids), batch_size):
                created_at = datetime.now(timezone.utc)
                row = NewsJob(kind="collect", source_id=source_id,
                              slug=await self._new_slug("collect", source_id=source_id, created_at=created_at),
                              created_at=created_at,
                              payload={"repair_item_ids": ids[start:start + batch_size]})
                self.db_session.add(row)
                await self.db_session.flush()
                rows.append(row)
            await self.db_session.commit()
            return rows

    async def latest_analyses(self, item_ids: list[int]) -> dict[int, NewsJob]:
        """Read the latest job for each item's current content, including explicit retries."""
        if not item_ids:
            return {}
        async with self.operation():
            rows = await self.db_session.scalars(
                select(NewsJob)
                .join(NewsItem, NewsJob.item_id == NewsItem.id)
                .where(
                    NewsItem.id.in_(item_ids), NewsJob.kind == "analyze",
                    NewsJob.payload["content_hash"].astext == NewsItem.content_hash,
                )
                .distinct(NewsJob.item_id)
                .order_by(NewsJob.item_id, NewsJob.id.desc())
            )
            return {row.item_id: row for row in rows}

    async def get(self, job_id: int) -> NewsJob | None:
        """Read safe job state; serialization deliberately excludes payload ownership."""
        async with self.operation():
            return await self.db_session.get(NewsJob, job_id)

    async def enqueue(
        self,
        kind: str,
        *,
        source_id: int | None = None,
        item_id: int | None = None,
        payload: dict | None = None,
        dedupe_key: str | None = None,
        retry_failed: bool = False,
    ) -> NewsJob:
        """Enqueue once per identity; only explicit retries revive terminal failures."""
        async with self.operation():
            if kind == "analyze" and item_id is not None and (payload or {}).get("content_hash"):
                # Manual repair and automatic backlog refresh must not race into two provider calls.
                await self.db_session.execute(
                    text("SELECT pg_advisory_xact_lock(:key)"), {"key": QUEUE_LOCK}
                )
                active = await self.db_session.scalar(select(NewsJob).where(
                    NewsJob.kind == "analyze", NewsJob.item_id == item_id,
                    NewsJob.status.in_(["queued", "running"]),
                    NewsJob.payload["content_hash"].astext == payload["content_hash"],
                ).order_by(NewsJob.id).limit(1))
                if active is not None:
                    if payload.get("force") and active.status == "queued":
                        active.payload = {**active.payload, "force": True}
                    await self.db_session.commit()
                    return active
            created_at = datetime.now(timezone.utc)
            values = dict(
                slug=await self._new_slug(kind, source_id=source_id, item_id=item_id, payload=payload, created_at=created_at),
                created_at=created_at,
                kind=kind,
                source_id=source_id,
                item_id=item_id,
                payload=payload or {},
                dedupe_key=dedupe_key,
            )
            if dedupe_key:
                row_id = await self.db_session.scalar(
                    insert(NewsJob)
                    .values(**values)
                    .on_conflict_do_nothing(index_elements=["dedupe_key"])
                    .returning(NewsJob.id)
                )
                row = await self.db_session.scalar(
                    select(NewsJob)
                    .where(NewsJob.dedupe_key == dedupe_key)
                    .with_for_update()
                )
                if (
                    row_id is None
                    and retry_failed
                    and row.status in {"failed", "cancelled"}
                ):
                    row.status, row.attempts, row.error, row.result = (
                        "queued",
                        0,
                        None,
                        None,
                    )
                    row.available_at, row.completed_at = (
                        datetime.now(timezone.utc),
                        None,
                    )
                    row.payload = payload or {}
            else:
                row = NewsJob(**values)
                self.db_session.add(row)
            await self.db_session.commit()
            return row

    async def enqueue_due_sources(self, *, now: datetime | None = None) -> list[NewsJob]:
        """Atomically queue one latest due start per verified, enabled source.

        A persistent next start advances beyond now in the same transaction as
        insertion. Restarts coalesce missed starts; concurrent schedulers share
        the source locks and the unique source/start identity.
        """
        now = now or datetime.now(timezone.utc)
        async with self.operation():
            locked = await self.db_session.scalar(
                text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": SCHEDULE_LOCK}
            )
            if not locked:
                await self.db_session.rollback()
                return []
            settings = await self.db_session.get(NewsSetting, 1)
            enabled = settings is None or settings.value.get("enabled", True)
            # Older global starts have no source scope and must not revive the removed calendar.
            await self.db_session.execute(
                update(NewsJob).where(
                    NewsJob.status == "queued", NewsJob.payload.has_key("scheduled_slot"),
                    NewsJob.source_id.is_(None),
                ).values(status="cancelled", completed_at=now, error="Global source calendar was replaced")
            )
            rows = list(await self.db_session.scalars(
                select(NewsSource).where(
                    NewsSource.profile_id.is_not(None), NewsSource.active.is_(True),
                    (NewsSource.next_check_at.is_(None) | (NewsSource.next_check_at <= now)),
                ).order_by(NewsSource.next_check_at, NewsSource.id)
                .with_for_update(skip_locked=True).execution_options(populate_existing=True)
            ))
            result: list[NewsJob] = []
            for source in rows:
                due_at = source.next_check_at
                source.next_check_at = next_scheduled_check(source.schedule, now)
                if not enabled or due_at is None:
                    continue
                slot = latest_scheduled_check(source.schedule, now)
                if slot is None or slot < due_at:
                    continue
                slot_key = slot.isoformat()
                await self.db_session.execute(
                    update(NewsJob).where(
                        NewsJob.source_id == source.id, NewsJob.status == "queued",
                        NewsJob.payload.has_key("scheduled_slot"),
                        NewsJob.dedupe_key != f"scheduled:{source.id}:{slot_key}",
                    ).values(status="cancelled", completed_at=now, error="Missed source starts were coalesced")
                )
                row_id = await self.db_session.scalar(
                    insert(NewsJob).values(
                        slug=await self._new_slug("collect", source_id=source.id, created_at=now),
                        created_at=now, kind="collect", source_id=source.id,
                        payload={"scheduled_slot": slot_key, "source_schedule": source.schedule},
                        dedupe_key=f"scheduled:{source.id}:{slot_key}",
                    ).on_conflict_do_nothing(index_elements=["dedupe_key"]).returning(NewsJob.id)
                )
                if row_id is not None:
                    result.append(await self.db_session.get(NewsJob, row_id))
            await self.db_session.commit()
            return result

    async def claim(
        self,
        owner_token: str,
        lease_seconds: int,
        max_attempts: int,
        *,
        kinds: list[str] | None = None,
        concurrency_limits: dict[str, int] | None = None,
    ) -> NewsJob | None:
        """Acquire the next available job with SKIP LOCKED and shared concurrency caps."""
        async with self.operation():
            await self.db_session.execute(
                text("SELECT pg_advisory_xact_lock(:key)"), {"key": QUEUE_LOCK}
            )
            settings = await self.db_session.get(NewsSetting, 1)
            registered_source = select(NewsSource.id).where(
                NewsSource.id == NewsJob.source_id, NewsSource.active.is_(True),
                NewsSource.profile_id.is_not(None),
                NewsSource.schedule == NewsJob.payload["source_schedule"],
            ).exists()
            obsolete = ~registered_source
            if settings is not None and not settings.value.get("enabled", True):
                obsolete = True
            await self.db_session.execute(
                update(NewsJob).where(
                    NewsJob.status == "queued", NewsJob.payload.has_key("scheduled_slot"), obsolete,
                ).values(status="cancelled", completed_at=func.now(), error="Automatic collection preferences changed")
            )
            kinds = kinds or ["collect", "discover", "analyze"]
            limits = concurrency_limits or {"collect": 1, "discover": 1, "analyze": 1}
            counts = dict(
                (
                    await self.db_session.execute(
                        select(NewsJob.kind, func.count())
                        .where(
                            NewsJob.status == "running",
                            NewsJob.lease_expires_at > func.now(),
                        )
                        .group_by(NewsJob.kind)
                    )
                ).all()
            )
            eligible = [
                kind for kind in kinds if counts.get(kind, 0) < limits.get(kind, 1)
            ]
            statement = (
                select(NewsJob)
                .where(
                    NewsJob.kind.in_(eligible),
                    NewsJob.status == "queued",
                    NewsJob.available_at <= func.now(),
                    NewsJob.attempts < max_attempts,
                )
                .order_by(NewsJob.created_at, NewsJob.id)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            row = await self.db_session.scalar(statement)
            if row is not None:
                now = datetime.now(timezone.utc)
                row.status, row.owner_token = "running", owner_token
                row.started_at, row.heartbeat_at = now, now
                row.lease_expires_at = now + timedelta(seconds=lease_seconds)
                row.attempts += 1
            await self.db_session.commit()
            return row

    @staticmethod
    def owned(job_id: int, owner_token: str):
        return (
            NewsJob.id == job_id,
            NewsJob.owner_token == owner_token,
            NewsJob.status == "running",
            NewsJob.lease_expires_at > func.now(),
        )

    async def heartbeat(
        self,
        job_id: int,
        owner_token: str,
        lease_seconds: int,
        progress: dict | None = None,
    ) -> bool:
        """Extend only a current lease; expired ownership cannot be revived."""
        async with self.operation():
            values = dict(
                heartbeat_at=func.now(),
                lease_expires_at=func.now() + timedelta(seconds=lease_seconds),
            )
            if progress is not None:
                values["progress"] = progress
            row_id = await self.db_session.scalar(
                update(NewsJob)
                .where(*self.owned(job_id, owner_token))
                .values(**values)
                .returning(NewsJob.id)
            )
            await self.db_session.commit()
            return row_id is not None

    async def complete(
        self,
        job_id: int,
        owner_token: str,
        result: dict | None = None,
        progress: dict | None = None,
    ) -> bool:
        """Commit a terminal result only for the owner of an unexpired lease."""
        async with self.operation():
            values = dict(
                status="completed",
                result=result,
                error=None,
                completed_at=func.now(),
                owner_token=None,
                lease_expires_at=None,
            )
            if progress is not None:
                values["progress"] = progress
            row_id = await self.db_session.scalar(
                update(NewsJob)
                .where(*self.owned(job_id, owner_token))
                .values(**values)
                .returning(NewsJob.id)
            )
            await self.db_session.commit()
            return row_id is not None

    async def fail(
        self,
        job_id: int,
        owner_token: str,
        error: str,
        retry: bool,
        max_attempts: int,
        retry_delay_seconds: int = 0,
    ) -> bool:
        """Retry transient failures within the cap; expose only safe error summaries."""
        async with self.operation():
            row = await self.db_session.scalar(
                select(NewsJob)
                .where(*self.owned(job_id, owner_token))
                .with_for_update()
            )
            if row is None:
                await self.db_session.rollback()
                return False
            queued = retry and row.attempts < max_attempts
            row.status, row.error = "queued" if queued else "failed", error[:500]
            row.available_at = datetime.now(timezone.utc) + timedelta(
                seconds=retry_delay_seconds
            )
            row.completed_at = None if queued else datetime.now(timezone.utc)
            row.owner_token, row.lease_expires_at = None, None
            await self.db_session.commit()
            return True

    async def release(self, job_id: int, owner_token: str) -> bool:
        """Requeue on graceful shutdown without consuming a failed attempt."""
        async with self.operation():
            row_id = await self.db_session.scalar(
                update(NewsJob)
                .where(*self.owned(job_id, owner_token))
                .values(
                    status="queued",
                    owner_token=None,
                    lease_expires_at=None,
                    attempts=func.greatest(NewsJob.attempts - 1, 0),
                )
                .returning(NewsJob.id)
            )
            await self.db_session.commit()
            return row_id is not None

    async def recover(self, max_attempts: int) -> int:
        """Recover expired owners after crashes and stop jobs that exhaust their cap."""
        async with self.operation():
            rows = list(
                (
                    await self.db_session.scalars(
                        select(NewsJob)
                        .where(
                            NewsJob.status == "running",
                            NewsJob.lease_expires_at <= func.now(),
                        )
                        .with_for_update(skip_locked=True)
                    )
                ).all()
            )
            for row in rows:
                row.status = "failed" if row.attempts >= max_attempts else "queued"
                row.error, row.owner_token, row.lease_expires_at = (
                    "Worker lease expired",
                    None,
                    None,
                )
                row.available_at = datetime.now(timezone.utc)
                row.completed_at = (
                    datetime.now(timezone.utc) if row.status == "failed" else None
                )
                await self.db_session.execute(
                    update(NewsSourceRun)
                    .where(
                        NewsSourceRun.job_id == row.id,
                        NewsSourceRun.status == "running",
                    )
                    .values(
                        status="failed",
                        error="Worker lease expired",
                        completed_at=func.now(),
                    )
                )
            await self.db_session.commit()
            return len(rows)
