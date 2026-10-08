"""PostgreSQL queue with atomic acquisition, ownership fencing and bounded retries."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert

from src.db.models.news_jobs import NewsJob, NewsSourceRun
from src.repositories.news_base import NewsRepository

QUEUE_LOCK = 721409081
SCHEDULE_LOCK = 721409082


class NewsJobRepository(NewsRepository):
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
            values = dict(
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

    async def enqueue_scheduled(self, slot_key: str) -> NewsJob | None:
        """Serialize schedulers and persist a unique schedule occurrence."""
        async with self.operation():
            locked = await self.db_session.scalar(
                text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": SCHEDULE_LOCK}
            )
            if not locked:
                await self.db_session.rollback()
                return None
            row_id = await self.db_session.scalar(
                insert(NewsJob)
                .values(
                    kind="collect",
                    payload={"scheduled_slot": slot_key},
                    dedupe_key=f"scheduled:{slot_key}",
                )
                .on_conflict_do_nothing(index_elements=["dedupe_key"])
                .returning(NewsJob.id)
            )
            row = await self.db_session.get(NewsJob, row_id) if row_id else None
            await self.db_session.commit()
            return row

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
