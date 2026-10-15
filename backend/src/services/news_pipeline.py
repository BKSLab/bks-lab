"""Durable news jobs with short repository scopes and fenced writes."""

import asyncio
import logging
from collections.abc import Callable, Sequence
from contextlib import AbstractAsyncContextManager, suppress
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from src.clients.news_sources import NewsSourceClient, prepare_collected_item
from src.core.news_settings import NewsSettings
from src.db.models.news_jobs import NewsJob
from src.db.models.news_sources import NewsSource
from src.exceptions.llm import LlmApiRequestError
from src.exceptions.news import NewsLeaseLostError, NewsRepositoryError, NewsSourceChangedError
from src.exceptions.news_sources import NewsSourceError
from src.news_sources import get_source_profile
from src.repositories.news_analyses import NewsAnalysisRepository
from src.repositories.news_catalog import NewsCatalogRepository
from src.repositories.news_items import NewsItemRepository
from src.repositories.news_jobs import NewsJobRepository
from src.repositories.news_runs import NewsRunRepository
from src.repositories.news_settings import NewsSettingsRepository
from src.repositories.news_sources import NewsSourceRepository
from src.schemas.news import NewsSettingsData
from src.schemas.news_collection import NEWS_MIN_CONTENT_CHARS, CollectedItem
from src.services.news_analysis import NEWS_PROMPT_VERSION, NewsAnalysisService

logger = logging.getLogger(__name__)
NEWS_COLLECTION_VERSION = "news-text-v3"


@dataclass(frozen=True)
class NewsRepositories:
    """A repository bundle whose owning context closes one short DB session."""

    jobs: NewsJobRepository
    sources: NewsSourceRepository
    items: NewsItemRepository
    analyses: NewsAnalysisRepository
    catalog: NewsCatalogRepository
    settings: NewsSettingsRepository
    runs: NewsRunRepository


RepositoryScope = Callable[[], AbstractAsyncContextManager[NewsRepositories]]


class NewsPipeline:
    """Orchestrate collection and AI analysis as independent durable jobs.

    Repository contexts never overlap a source or provider network call. A lost
    lease cancels work, and both ingest and analysis writes check ownership again
    in their database transaction.
    """

    def __init__(
        self,
        *,
        repositories: RepositoryScope,
        collector: NewsSourceClient,
        analyzer: NewsAnalysisService | None,
        config: NewsSettings,
        utc_now: Callable[[], datetime],
    ) -> None:
        self._repositories = repositories
        self._collector = collector
        self._analyzer = analyzer
        self._config = config
        self._utc_now = utc_now
        self._source_gate = asyncio.Semaphore(config.http_concurrency)

    async def get_settings(self) -> dict[str, Any]:
        """Combine environment defaults with the administrator's stored policy."""
        names = (
            "enabled", "initial_lookback_days",
            "max_items_per_source", "max_excerpt_chars", "analysis_batch_size",
            "text_retention_days", "history_retention_days",
        )
        defaults = {name: getattr(self._config, name) for name in names}
        async with self._repositories() as repositories:
            stored = await repositories.settings.get()
        supported = {key: value for key, value in stored.items() if key in NewsSettingsData.model_fields}
        return NewsSettingsData.model_validate({**defaults, **supported}).model_dump()

    async def enqueue_scheduled(self) -> None:
        """Enqueue due source calendars atomically across scheduler processes."""
        if not (await self.get_settings())["enabled"]:
            return
        async with self._repositories() as repositories:
            await repositories.jobs.enqueue_due_sources(now=self._utc_now())

    async def recover(self) -> int:
        """Requeue expired leases, respecting the finite job retry limit."""
        async with self._repositories() as repositories:
            recovered = await repositories.jobs.recover(self._config.job_max_attempts)
        if recovered:
            logger.warning("Recovered %s expired news jobs", recovered)
        return recovered

    async def enqueue_pending(self, policy: dict[str, Any]) -> int:
        """Resume a bounded pending backlog without reviving exhausted jobs."""
        if not self._config.llm_configured or not policy["enabled"]:
            return 0
        async with self._repositories() as repositories:
            pending = await repositories.items.pending(
                limit=policy["analysis_batch_size"],
                model=self._config.llm_model,
                prompt_version=NEWS_PROMPT_VERSION,
            )
        for item in pending:
            async with self._repositories() as repositories:
                await repositories.jobs.enqueue(
                    "analyze", item_id=item.id,
                    dedupe_key=self._analysis_key(item.id, item.content_hash),
                    payload={"content_hash": item.content_hash},
                )
        return len(pending)

    async def retain(self, policy: dict[str, Any]) -> dict[str, int]:
        """Expire source text and operational history according to policy."""
        now = self._utc_now()
        async with self._repositories() as repositories:
            return await repositories.items.retain(
                text_before=now - timedelta(days=policy["text_retention_days"]),
                history_before=now - timedelta(days=policy["history_retention_days"]),
            )

    async def run_once(self, kinds: Sequence[str]) -> bool:
        """Claim and handle one job; return false when this lane has no work."""
        allowed = [kind for kind in kinds if kind != "analyze" or self._analyzer is not None]
        if not allowed:
            return False
        owner = uuid4().hex
        async with self._repositories() as repositories:
            job = await repositories.jobs.claim(
                owner_token=owner,
                lease_seconds=self._config.lease_seconds,
                max_attempts=self._config.job_max_attempts,
                kinds=allowed,
                concurrency_limits={
                    "collect": 1, "discover": 1,
                    "analyze": self._config.llm_concurrency,
                },
            )
        if job is None:
            return False
        progress: dict[str, Any] = {}
        work = asyncio.create_task(self._execute(job, owner, progress))
        heartbeat = asyncio.create_task(self._heartbeat(job.id, owner, progress))
        try:
            done, _ = await asyncio.wait((work, heartbeat), return_when=asyncio.FIRST_COMPLETED)
            if heartbeat in done:
                work.cancel()
                with suppress(asyncio.CancelledError, Exception):
                    await work
                # Failure to renew makes ownership uncertain. Only recovery may
                # release that lease; this worker must not commit a result.
                with suppress(Exception):
                    heartbeat.result()
                logger.warning("News job %s lost its lease", job.id)
                return True
            result = await work
            async with self._repositories() as repositories:
                completed = await repositories.jobs.complete(job.id, owner, result=result, progress=progress)
            if completed:
                logger.info("Completed news job %s (%s)", job.id, job.kind)
            else:
                logger.warning("News job %s no longer belongs to this worker", job.id)
        except asyncio.CancelledError:
            work.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await work
            try:
                async with self._repositories() as repositories:
                    await repositories.jobs.release(job.id, owner)
            except Exception as error:
                logger.warning("Could not release news job %s (%s)", job.id, type(error).__name__)
            raise
        except Exception as error:
            message, retryable = self._safe_error(error)
            logger.warning("News job %s failed (%s)", job.id, type(error).__name__)
            async with self._repositories() as repositories:
                await repositories.jobs.fail(
                    job.id, owner, error=message, retry=retryable,
                    max_attempts=self._config.job_max_attempts,
                    retry_delay_seconds=self._config.job_retry_delay_seconds,
                )
        finally:
            heartbeat.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await heartbeat
        return True

    async def _heartbeat(self, job_id: int, owner: str, progress: dict[str, Any]) -> None:
        while True:
            await asyncio.sleep(self._config.heartbeat_seconds)
            async with self._repositories() as repositories:
                renewed = await repositories.jobs.heartbeat(
                    job_id, owner, self._config.lease_seconds, progress=dict(progress)
                )
            if not renewed:
                return

    async def _execute(self, job: NewsJob, owner: str, progress: dict[str, Any]) -> dict[str, Any]:
        policy = await self.get_settings()
        if job.kind == "discover":
            preview = await self._collector.discover(
                url=job.payload["url"], kind=job.payload.get("kind"),
                config=job.payload.get("config"),
            )
            return preview.to_dict()
        if job.kind == "collect":
            if job.dedupe_key and job.dedupe_key.startswith("scheduled:") and not policy["enabled"]:
                return {"skipped": "disabled"}
            return await self._collect(job, owner, progress, policy)
        if job.kind == "analyze":
            return await self._analyze(job, owner, policy)
        raise ValueError("Unknown news job kind")

    async def _collect(
        self, job: NewsJob, owner: str, progress: dict[str, Any], policy: dict[str, Any],
    ) -> dict[str, Any]:
        async with self._repositories() as repositories:
            if job.source_id is not None:
                source = await repositories.sources.get(job.source_id)
                sources = [source] if source is not None else []
            else:
                sources = await repositories.sources.list_active()
        started_at = self._collection_time(job)
        if job.payload.get("scheduled_slot"):
            sources = [
                source for source in sources
                if source.active and source.profile_id is not None
                and source.schedule == job.payload.get("source_schedule")
            ]
        sources = [source for source in sources if source.profile_id is not None]
        progress.update(sources_total=len(sources), sources_done=0, new=0, updated=0, unchanged=0, skipped=0, errors=0, warnings=0)
        results = await asyncio.gather(
            *(self._collect_source(source, job, owner, progress, policy, started_at) for source in sources),
            return_exceptions=True,
        )
        failures: list[Exception] = []
        for result in results:
            if isinstance(result, asyncio.CancelledError):
                raise result
            if isinstance(result, Exception):
                failures.append(result)
        if failures and len(failures) == len(sources):
            raise NewsSourceError(
                "all_sources_failed", "Не удалось получить материалы из выбранных источников.",
                retryable=any(self._safe_error(error)[1] for error in failures),
            )
        await self.enqueue_pending(policy)
        return dict(progress)

    async def _collect_source(
        self, source: NewsSource, job: NewsJob, owner: str,
        progress: dict[str, Any], policy: dict[str, Any], started_at: datetime,
    ) -> dict[str, Any]:
        async with self._source_gate:
            async with self._repositories() as repositories:
                known_urls = await repositories.items.known_urls(source.id)
                first_completed = (
                    await repositories.runs.first_completed_at(source.id)
                    if source.last_success_at is not None else None
                )
                cursor = source.cursor or {}
                cutoff = self._collection_cutoff(source, policy, first_completed)
                profile = get_source_profile(source.profile_id)
                profile_version = profile.version if profile is not None else None
                current_parser = (
                    cursor.get("collection_version") == NEWS_COLLECTION_VERSION
                    and cursor.get("profile_version") == profile_version
                )
                repair_ids = job.payload.get("repair_item_ids")
                run = await repositories.runs.begin(
                    source.id, job.id, owner_token=owner,
                    parameters={
                        "cutoff": cutoff.isoformat(),
                        "initial_lookback_days": policy["initial_lookback_days"],
                        "max_items_per_source": policy["max_items_per_source"],
                        "max_excerpt_chars": policy["max_excerpt_chars"],
                        "first_run": source.last_success_at is None,
                        "conditional_request": bool(current_parser and (source.etag or source.last_modified)),
                        "mode": "repair" if repair_ids is not None else "collect",
                        "trigger": "scheduled" if job.payload.get("scheduled_slot") else "manual",
                    },
                )
            try:
                if repair_ids is not None:
                    async with self._repositories() as repositories:
                        previous_items = await repositories.items.repair_batch(source.id, repair_ids)
                    collected = await self._collector.refetch([
                        CollectedItem(
                            external_id=item.external_id, url=item.url,
                            canonical_url=item.canonical_url or item.url, title=item.title,
                            published_at=item.published_at, updated_at=item.updated_at,
                            metadata=item.metadata_json or {},
                        ) for item in previous_items
                    ], max_excerpt_chars=policy["max_excerpt_chars"], profile_id=source.profile_id)
                else:
                    collected = await self._collector.fetch_profile(
                        profile_id=source.profile_id,
                        etag=source.etag if current_parser else None,
                        last_modified=source.last_modified if current_parser else None,
                        first_run=source.last_success_at is None,
                        cutoff=cutoff, known_urls=known_urls,
                        max_items=policy["max_items_per_source"],
                        lookback_days=policy["initial_lookback_days"],
                        max_excerpt_chars=policy["max_excerpt_chars"],
                    )
                items = [prepare_collected_item(item) for item in collected.items]
                if repair_ids is not None:
                    for previous, values in zip(previous_items, items, strict=True):
                        values["existing_item_id"] = previous.id
                for item in items:
                    item["content"] = item["content"][:policy["max_excerpt_chars"]]
                    item["excerpt"] = item["excerpt"][:policy["max_excerpt_chars"]]
                warnings = [
                    item for item in items
                    if item["metadata_json"].get("collection_status") in {"insufficient_text", "fetch_failed"}
                    or max(len(item["content"]), len(item["excerpt"])) < NEWS_MIN_CONTENT_CHARS
                ]
                warning = (
                    "Не удалось получить полный текст части материалов; проверьте предупреждения в карточках."
                    if warnings or collected.warnings else None
                )
                async with self._repositories() as repositories:
                    counts = await repositories.items.ingest(
                        source.id, items,
                        cursor={
                            **cursor, "collected_at": started_at.isoformat(),
                            "initial_cutoff_at": cutoff.isoformat(),
                            "collection_version": NEWS_COLLECTION_VERSION,
                            "profile_version": profile_version,
                        },
                        etag=collected.etag if warning is None else None,
                        last_modified=collected.last_modified if warning is None else None,
                        job_id=job.id, owner_token=owner,
                        expected_url=source.url, expected_kind=source.kind,
                        expected_config=source.config,
                        collection_warning=warning,
                        run_id=run.id, skipped=collected.skipped,
                        run_diagnostics={
                            "warning_count": len(warnings) or int(bool(collected.warnings)),
                            "http_status": collected.http_status, "not_modified": collected.not_modified,
                            "limit_reached": collected.limit_reached,
                            "diagnostics_truncated": collected.diagnostics_truncated,
                        },
                    )
                for key in ("new", "updated", "unchanged"):
                    progress[key] += counts[key]
                progress["warnings"] += len(warnings) or int(bool(collected.warnings))
                progress["skipped"] += len(collected.skipped)
                if repair_ids is not None and self._config.llm_configured:
                    for item_id in counts["item_ids"]:
                        async with self._repositories() as repositories:
                            item = await repositories.items.get(item_id)
                            if (
                                item is not None and item.duplicate_of_id is None
                                and not (item.metadata_json or {}).get("collection_warning")
                                and max(len(item.content), len(item.excerpt)) >= NEWS_MIN_CONTENT_CHARS
                            ):
                                await repositories.jobs.enqueue(
                                    "analyze", item_id=item_id,
                                    dedupe_key=f"repair:{job.id}:{self._analysis_key(item_id, item.content_hash)}",
                                    payload={"content_hash": item.content_hash, "force": True},
                                )
                return counts
            except asyncio.CancelledError:
                with suppress(NewsRepositoryError, OSError):
                    async with self._repositories() as repositories:
                        await repositories.runs.finish(
                            run.id, "cancelled", job_id=job.id, owner_token=owner,
                        )
                raise
            except NewsLeaseLostError:
                raise
            except NewsSourceChangedError:
                async with self._repositories() as repositories:
                    await repositories.runs.finish(
                        run.id, "cancelled", job_id=job.id, owner_token=owner,
                        error="Настройки источника изменились во время обхода.",
                    )
                raise
            except Exception as error:
                message, _ = self._safe_error(error)
                progress["errors"] += 1
                async with self._repositories() as repositories:
                    await repositories.sources.mark_error(
                        source.id, message, job_id=job.id, owner_token=owner,
                    )
                    await repositories.runs.finish(
                        run.id, "failed", error=message, job_id=job.id, owner_token=owner,
                    )
                logger.warning("News source %s failed (%s)", source.id, type(error).__name__)
                raise
            finally:
                progress["sources_done"] += 1

    async def _analyze(self, job: NewsJob, owner: str, policy: dict[str, Any]) -> dict[str, Any]:
        async with self._repositories() as repositories:
            item = await repositories.items.get(job.item_id)
            if item is None or item.duplicate_of_id is not None:
                return {"skipped": "missing_or_duplicate"}
            expected_hash = job.payload.get("content_hash")
            if expected_hash and expected_hash != item.content_hash:
                return {"skipped": "content_changed"}
            if (
                not job.payload.get("force") and item.analysis is not None
                and item.analysis.content_hash == item.content_hash
                and item.analysis.model == self._config.llm_model
                and item.analysis.prompt_version == NEWS_PROMPT_VERSION
            ):
                return {"analysis_id": item.analysis.id}
            if max(len(item.content), len(item.excerpt)) < NEWS_MIN_CONTENT_CHARS:
                raise NewsSourceError(
                    "insufficient_text", "Недостаточно текста для анализа. Повторите сбор источника.",
                    retryable=False,
                )
            source = await repositories.sources.get(item.source_id)
            categories = await repositories.catalog.list("categories", active_only=True)
            topics = await repositories.catalog.list("topics", active_only=True)
            item_data = {name: getattr(item, name) for name in (
                "id", "url", "title", "excerpt", "content", "published_at", "content_hash",
            )}
            source_data = {name: getattr(source, name) for name in (
                "id", "name", "trust_score", "vendor_affiliated",
            )}
            category_data = [{"id": row.id, "name": row.name, "description": row.description} for row in categories]
            topic_data = [{"id": row.id, "name": row.name, "description": row.description} for row in topics]
        if self._analyzer is None:
            raise RuntimeError("An analysis job requires a configured analyzer")
        result = await self._analyzer.analyze(
            item=item_data, source=source_data, categories=category_data,
            topics=topic_data, settings=policy,
        )
        async with self._repositories() as repositories:
            saved = await repositories.analyses.save(
                item_id=item.id, content_hash=item.content_hash,
                model=self._config.llm_model, prompt_version=NEWS_PROMPT_VERSION,
                data=result, job_id=job.id, owner_token=owner,
                replace_existing=bool(job.payload.get("force")),
            )
        return {"analysis_id": saved.id} if saved is not None else {"skipped": "content_changed"}

    def _analysis_key(self, item_id: int, content_hash: str) -> str:
        return f"analysis:{item_id}:{content_hash}:{self._config.llm_model}:{NEWS_PROMPT_VERSION}"

    def _collection_cutoff(
        self, source: NewsSource, policy: dict[str, Any], first_completed: datetime | None,
    ) -> datetime:
        """Keep the first import boundary stable across later collections and policy changes."""
        recorded = (source.cursor or {}).get("initial_cutoff_at")
        if isinstance(recorded, str):
            try:
                cutoff = datetime.fromisoformat(recorded)
                if cutoff.tzinfo is not None:
                    return cutoff
            except ValueError:
                pass
        initial = first_completed or source.last_success_at or self._utc_now()
        return initial - timedelta(days=policy["initial_lookback_days"])

    def _collection_time(self, job: NewsJob) -> datetime:
        """Keep a delayed run tied to its nominal UTC calendar occurrence."""
        now = self._utc_now()
        slot = job.payload.get("scheduled_slot")
        if isinstance(slot, str):
            try:
                scheduled = datetime.fromisoformat(slot)
                if scheduled.tzinfo is not None:
                    return min(scheduled.astimezone(timezone.utc), now)
            except ValueError:
                pass
        return now

    @staticmethod
    def _safe_error(error: Exception) -> tuple[str, bool]:
        if isinstance(error, NewsSourceError):
            return str(error), error.retryable
        if isinstance(error, LlmApiRequestError):
            return error.detail, error.retryable
        return "Не удалось обработать задание. Повторите попытку позже.", True
