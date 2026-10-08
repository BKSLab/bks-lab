"""Dedicated APScheduler process; this module is never loaded by FastAPI."""

import asyncio
import logging
import signal
from collections.abc import AsyncIterator, Callable, Sequence
from contextlib import AsyncExitStack, asynccontextmanager, suppress
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.core.logging import setup_logging
from src.core.news_settings import NewsSettings
from src.core.settings import get_settings
from src.services.news_pipeline import NewsPipeline, NewsRepositories

logger = logging.getLogger(__name__)


def latest_scheduled_slot(
    now: datetime, schedule: Sequence[str], timezone_name: str,
) -> str:
    """Identify the latest wall-clock slot, including one coalesced missed run.

    A local date/time key intentionally identifies both folds of a DST fallback
    as the same daily start. A nonexistent spring-forward time is caught up by
    the settings refresh after the gap.
    """
    local_now = now.astimezone(ZoneInfo(timezone_name))
    date = local_now.date()
    current_time = local_now.strftime("%H:%M")
    due = [value for value in sorted(schedule) if value <= current_time]
    if due:
        slot = due[-1]
    else:
        date -= timedelta(days=1)
        slot = max(schedule)
    return f"{timezone_name}:{date.isoformat()}:{slot}"


class NewsScheduler:
    """Manage daily triggers and queue workers without holding DB resources."""

    def __init__(
        self,
        *,
        pipeline: NewsPipeline,
        scheduler: AsyncIOScheduler,
        config: NewsSettings,
        utc_now: Callable[[], datetime],
    ) -> None:
        self._pipeline = pipeline
        self._scheduler = scheduler
        self._config = config
        self._utc_now = utc_now
        self._stop = asyncio.Event()
        self._workers: list[asyncio.Task[None]] = []
        self._signature: tuple[Any, ...] | None = None
        self._refresh_lock = asyncio.Lock()

    async def start(self) -> None:
        """Check PostgreSQL, recover leases and start only after a valid policy."""
        await asyncio.to_thread(self._config.health_file.unlink, missing_ok=True)
        await self.refresh()
        self._scheduler.add_job(
            self.refresh, "interval", seconds=self._config.settings_refresh_seconds,
            id="news-settings", max_instances=1, coalesce=True,
            misfire_grace_time=None,
        )
        self._scheduler.add_job(
            self.maintenance, "interval", seconds=self._config.maintenance_interval_seconds,
            id="news-retention", max_instances=1, coalesce=True,
            misfire_grace_time=None,
        )
        self._scheduler.start()
        self._workers = [asyncio.create_task(self._consume(("collect", "discover")))]
        if self._config.llm_configured:
            self._workers.extend(
                asyncio.create_task(self._consume(("analyze",)))
                for _ in range(self._config.llm_concurrency)
            )
        logger.info("News scheduler started; AI analysis configured=%s", self._config.llm_configured)

    async def refresh(self) -> None:
        """Reconcile DB policy, catch up one missed slot and renew local health."""
        async with self._refresh_lock:
            policy = await self._pipeline.get_settings()
            signature = (policy["enabled"], policy["timezone"], tuple(policy["schedule"]))
            if signature != self._signature:
                for job in self._scheduler.get_jobs():
                    if job.id.startswith("news-daily-"):
                        self._scheduler.remove_job(job.id)
                if policy["enabled"]:
                    for index, slot in enumerate(policy["schedule"]):
                        hour, minute = map(int, slot.split(":"))
                        self._scheduler.add_job(
                            self.refresh,
                            CronTrigger(hour=hour, minute=minute, timezone=policy["timezone"]),
                            id=f"news-daily-{index}", max_instances=1, coalesce=True,
                            misfire_grace_time=None,
                        )
                self._signature = signature
            await self._pipeline.recover()
            if policy["enabled"]:
                await self._pipeline.enqueue_scheduled(latest_scheduled_slot(
                    self._utc_now(), policy["schedule"], policy["timezone"],
                ))
                await self._pipeline.enqueue_pending(policy)
            await asyncio.to_thread(self._config.health_file.touch)

    async def maintenance(self) -> None:
        """Apply retention independently from source/LLM availability."""
        policy = await self._pipeline.get_settings()
        counts = await self._pipeline.retain(policy)
        logger.info("News retention completed: %s", counts)

    async def stop(self) -> None:
        """Drain active jobs, then cancel and release remaining owned leases."""
        self._stop.set()
        if self._scheduler.running:
            self._scheduler.pause()
        if self._workers:
            _, pending = await asyncio.wait(self._workers, timeout=self._config.shutdown_grace_seconds)
            for worker in pending:
                worker.cancel()
            await asyncio.gather(*self._workers, return_exceptions=True)
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            # AsyncIOScheduler posts shutdown to the event loop.
            await asyncio.sleep(0)
        await asyncio.to_thread(self._config.health_file.unlink, missing_ok=True)
        logger.info("News scheduler stopped")

    async def _consume(self, kinds: Sequence[str]) -> None:
        while not self._stop.is_set():
            try:
                worked = await self._pipeline.run_once(kinds)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                # Unknown provider/DB exceptions may include connection details;
                # the exception type is sufficient for operational diagnostics.
                logger.error("News queue worker iteration failed (%s)", type(error).__name__)
                worked = False
            if not worked:
                with suppress(TimeoutError):
                    await asyncio.wait_for(self._stop.wait(), self._config.queue_poll_seconds)


async def run_scheduler() -> None:
    """Compose process-scoped clients and per-operation repository contexts."""
    # Keep startup-only infrastructure imports outside all HTTP-worker modules.
    from src.db.session import async_session_factory, engine
    from src.dependencies.news_clients import news_analysis_service, news_source_client
    from src.repositories.news_analyses import NewsAnalysisRepository
    from src.repositories.news_catalog import NewsCatalogRepository
    from src.repositories.news_items import NewsItemRepository
    from src.repositories.news_jobs import NewsJobRepository
    from src.repositories.news_runs import NewsRunRepository
    from src.repositories.news_settings import NewsSettingsRepository
    from src.repositories.news_sources import NewsSourceRepository

    settings = get_settings()
    config = settings.news
    setup_logging(settings.app.log_level)
    # HTTP libraries can log full request URLs; application errors are redacted.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    @asynccontextmanager
    async def repositories() -> AsyncIterator[NewsRepositories]:
        async with async_session_factory() as session:
            yield NewsRepositories(
                jobs=NewsJobRepository(session), sources=NewsSourceRepository(session),
                items=NewsItemRepository(session), analyses=NewsAnalysisRepository(session),
                catalog=NewsCatalogRepository(session), settings=NewsSettingsRepository(session),
                runs=NewsRunRepository(session),
            )

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def request_stop(*_: Any) -> None:
        loop.call_soon_threadsafe(stop_event.set)

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, request_stop)
        except NotImplementedError:
            signal.signal(sig, request_stop)

    try:
        async with AsyncExitStack() as stack:
            collector = await stack.enter_async_context(news_source_client(config))
            analyzer = (
                await stack.enter_async_context(news_analysis_service(config))
                if config.llm_configured else None
            )
            pipeline = NewsPipeline(
                repositories=repositories, collector=collector, analyzer=analyzer,
                config=config, utc_now=lambda: datetime.now(timezone.utc),
            )
            runner = NewsScheduler(
                pipeline=pipeline,
                scheduler=AsyncIOScheduler(timezone=config.timezone),
                config=config, utc_now=lambda: datetime.now(timezone.utc),
            )
            try:
                await runner.start()
                await stop_event.wait()
            finally:
                await runner.stop()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_scheduler())
