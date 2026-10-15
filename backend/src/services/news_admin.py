"""Editorial use cases for News Analyzer; no network work runs in API requests."""

from typing import Any

from pydantic import ValidationError

from src.core.news_settings import NewsSettings
from src.exceptions.news import (
    NewsInsufficientTextError,
    NewsNotFoundError,
    NewsValidationError,
)
from src.repositories.news_analyses import NewsAnalysisRepository
from src.repositories.news_catalog import CatalogKind, NewsCatalogRepository
from src.repositories.news_decisions import NewsDecisionRepository
from src.repositories.news_items import NewsItemRepository
from src.repositories.news_jobs import NewsJobRepository
from src.repositories.news_runs import NewsRunRepository
from src.repositories.news_settings import NewsSettingsRepository
from src.repositories.news_sources import NewsSourceRepository
from src.schemas.news import (
    AnalysisRow,
    CatalogCreate,
    CatalogPatch,
    CatalogRow,
    CollectRequest,
    DecisionRequest,
    DecisionRow,
    ItemDetail,
    ItemRow,
    JobRow,
    NewsSettingsData,
    QueuedJob,
    RunRow,
    RunItemRow,
    SettingsPatch,
    SettingsRow,
    SourcePatch,
    SourceRow,
)
from src.schemas.pagination import Paged
from src.schemas.news_collection import NEWS_MIN_CONTENT_CHARS
from src.schemas.news_collection_status import (
    CollectionAnalysisStatus,
    CollectionJobStatus,
    CollectionSourceStatus,
    CollectionStatus,
)


class NewsAdminService:
    """Compose repository operations and explicitly allow safe repository errors to propagate."""

    def __init__(
        self,
        *,
        sources: NewsSourceRepository,
        catalog: NewsCatalogRepository,
        items: NewsItemRepository,
        analyses: NewsAnalysisRepository,
        decisions: NewsDecisionRepository,
        jobs: NewsJobRepository,
        runs: NewsRunRepository,
        settings: NewsSettingsRepository,
        config: NewsSettings,
    ) -> None:
        self.sources, self.catalog, self.items = sources, catalog, items
        self.analyses, self.decisions, self.jobs = analyses, decisions, jobs
        self.runs, self.settings, self.config = runs, settings, config

    @staticmethod
    def source_row(row: Any) -> SourceRow:
        return SourceRow(**{key: getattr(row, key) for key in SourceRow.model_fields})

    @staticmethod
    def analysis_row(row: Any) -> AnalysisRow:
        return AnalysisRow(
            **{
                key: getattr(row, key)
                for key in AnalysisRow.model_fields
                if key not in {"topics", "category_name"}
            },
            category_name=row.category.name if row.category else None,
            topics=[CatalogRow.model_validate(topic) for topic in row.topics],
        )

    @classmethod
    def item_row(cls, row: Any, job: Any = None) -> ItemRow:
        text_length = max(len(row.content), len(row.excerpt))
        # Text retention may remove a previously analyzed body; that does not invalidate its result.
        insufficient = text_length < NEWS_MIN_CONTENT_CHARS and (text_length > 0 or not row.analysis)
        if insufficient:
            state = "insufficient_text"
        elif job is not None and job.status in {"queued", "running", "failed", "cancelled"}:
            state = "failed" if job.status == "cancelled" else job.status
        else:
            state = "analyzed" if row.analysis else "pending"
        return ItemRow(
            **{
                key: getattr(row, key)
                for key in ItemRow.model_fields
                if key not in {"source_name", "source_slug", "analysis", "decision", "analysis_state", "analysis_error", "collection_warning"}
            },
            source_name=row.source.name,
            source_slug=row.source.slug,
            analysis=cls.analysis_row(row.analysis) if row.analysis else None,
            decision=DecisionRow.model_validate(row.decision) if row.decision else None,
            analysis_state=state,
            analysis_error=(job.error or "Анализ не завершён. Можно повторить попытку.") if state == "failed" else None,
            collection_warning=(row.metadata_json or {}).get("collection_warning"),
        )

    async def list_sources(self) -> list[SourceRow]:
        """Read verified source profiles and their collection preferences."""
        return [self.source_row(row) for row in await self.sources.list()]

    async def get_source(self, source_slug: str) -> SourceRow:
        """Read source configuration by its stable public address."""
        source = await self.sources.get_by_slug(source_slug)
        if source is None or source.profile_id is None:
            raise NewsNotFoundError
        return self.source_row(source)

    async def update_source(self, source_slug: str, data: SourcePatch) -> SourceRow:
        """Update only source enablement and its individual collection calendar."""
        source = await self.sources.get_by_slug(source_slug)
        if source is None or source.profile_id is None:
            raise NewsNotFoundError
        values = data.model_dump(exclude_unset=True, mode="json")
        row = await self.sources.update_preferences(source.id, values)
        if row is None:
            raise NewsNotFoundError
        return self.source_row(row)

    async def list_catalog(self, kind: CatalogKind) -> list[CatalogRow]:
        """Read editable taxonomy including paused entries."""
        return [CatalogRow.model_validate(row) for row in await self.catalog.list(kind)]

    async def create_catalog(
        self, kind: CatalogKind, data: CatalogCreate
    ) -> CatalogRow:
        """Add a taxonomy entry for future classifications."""
        return CatalogRow.model_validate(
            await self.catalog.create(kind, data.model_dump())
        )

    async def update_catalog(
        self, kind: CatalogKind, row_id: int, data: CatalogPatch
    ) -> CatalogRow:
        """Edit a taxonomy entry without removing analysis history."""
        row = await self.catalog.update(
            kind, row_id, data.model_dump(exclude_unset=True)
        )
        if row is None:
            raise NewsNotFoundError
        return CatalogRow.model_validate(row)

    async def list_items(
        self, *, page: int, page_size: int, **filters: Any
    ) -> Paged[ItemRow]:
        """Read the current editorial queue, including pending items when unfiltered."""
        if (
            filters.get("date_from")
            and filters.get("date_to")
            and filters["date_from"] > filters["date_to"]
        ):
            raise NewsValidationError
        source_slug = filters.pop("source_slug", None)
        if source_slug is not None:
            source = await self.sources.get_by_slug(source_slug)
            if source is None:
                raise NewsNotFoundError
            filters["source_id"] = source.id
        rows, total = await self.items.list_page(
            page=page, page_size=page_size, **filters
        )
        jobs = await self.jobs.latest_analyses([row.id for row in rows])
        return Paged[ItemRow].build(
            [self.item_row(row, jobs.get(row.id)) for row in rows], total, page, page_size
        )

    async def get_item(self, item_id: int) -> ItemDetail:
        """Read retained text and complete available editorial history."""
        row = await self.items.get(item_id)
        if row is None:
            raise NewsNotFoundError
        analyses = await self.analyses.list_for_item(item_id)
        decisions = await self.decisions.list_for_item(item_id)
        jobs = await self.jobs.latest_analyses([item_id])
        return ItemDetail(
            **self.item_row(row, jobs.get(item_id)).model_dump(),
            content=row.content,
            analysis_history=[self.analysis_row(item) for item in analyses],
            decision_history=[DecisionRow.model_validate(item) for item in decisions],
        )

    async def decide(
        self, item_id: int, data: DecisionRequest, editor: str
    ) -> DecisionRow:
        """Append a decision attributed exclusively to the authenticated session."""
        row = await self.decisions.create(
            item_id, {**data.model_dump(), "editor": editor}
        )
        if row is None:
            raise NewsNotFoundError
        return DecisionRow.model_validate(row)

    async def reanalyze(self, item_id: int) -> QueuedJob:
        """Queue an explicit fresh attempt that may replace the same analysis identity."""
        item = await self.items.get(item_id)
        if item is None:
            raise NewsNotFoundError
        if max(len(item.content), len(item.excerpt)) < NEWS_MIN_CONTENT_CHARS:
            raise NewsInsufficientTextError
        job = await self.jobs.enqueue(
            "analyze",
            item_id=item_id,
            payload={"content_hash": item.content_hash, "force": True},
        )
        return QueuedJob(job_id=job.id, job_slug=job.slug, status=job.status)

    async def collect(self, data: CollectRequest) -> QueuedJob:
        """Queue a collection run with an optional existing source scope."""
        source = await self.sources.get_by_slug(data.source_slug) if data.source_slug is not None else None
        if data.source_slug is not None and (source is None or source.profile_id is None):
            raise NewsNotFoundError
        job = await self.jobs.enqueue("collect", source_id=source.id if source else None)
        return QueuedJob(job_id=job.id, job_slug=job.slug, status=job.status)

    async def collection_status(self, job_slug: str | None = None) -> CollectionStatus:
        """Restore collection and exact-version analysis progress from durable records.

        Args:
            job_slug: Optional explicit collection, including one just queued by the caller.

        Returns:
            Safe source and overall counters; unschedulable analysis never implies activity.

        Raises:
            NewsNotFoundError: An explicit address is missing or is not a collection.
        """
        stored = await self.settings.get()
        enabled = stored.get("enabled", self.config.enabled)
        selected, active_count = await self.jobs.collection_status_context(
            llm_configured=self.config.llm_configured, auto_enabled=enabled,
        )
        job = await self.jobs.get_by_slug(job_slug) if job_slug is not None else selected
        if job_slug is not None and (job is None or job.kind != "collect"):
            raise NewsNotFoundError
        result = CollectionStatus(active_jobs=active_count)
        if job is None:
            return result
        source = job.source
        result.job = CollectionJobStatus(
            slug=job.slug, status=job.status,
            source_slug=source.slug if source else None,
            source_name=source.name if source else None,
            created_at=job.created_at, started_at=job.started_at,
            completed_at=job.completed_at, error=job.error,
        )
        runs = await self.runs.latest_for_job(job.id)
        targets = {
            target["source_id"]: (target["source_slug"], target["source_name"])
            for target in job.payload.get("collection_targets", [])
        }
        if source is not None:
            targets[source.id] = (source.slug, source.name)
        elif "collection_targets" not in job.payload and job.status in {"queued", "running"}:
            # Existing jobs predate scope snapshots; their recorded attempts remain authoritative.
            targets.update({row.id: (row.slug, row.name) for row in await self.sources.list_active()})
        targets.update({run.source_id: (run.source_slug, run.source_name) for run in runs})
        latest = {run.source_id: run for run in runs}
        statuses: dict[int, CollectionSourceStatus] = {}
        for source_id, (slug, name) in targets.items():
            run = latest.get(source_id)
            state = run.status if run else "queued"
            error = run.error if run else None
            if state == "running" and job.status != "running":
                state = job.status if job.status in {"queued", "failed", "cancelled"} else "failed"
            if state == "running" and job.started_at and run.started_at < job.started_at:
                state = "queued"
            if run is None and job.status not in {"queued", "running"}:
                state = "failed" if job.status == "failed" else "cancelled"
                error = job.error or "Источник не был обработан в этом задании."
            statuses[source_id] = CollectionSourceStatus(
                source_slug=slug, source_name=name, status=state,
                new=run.new_count if run else 0, updated=run.updated_count if run else 0,
                unchanged=run.unchanged_count if run else 0, skipped=run.skipped_count if run else 0,
                warnings=run.warning_count if run else 0, error=error,
            )
        observations = await self.runs.observed_analysis_versions([run.id for run in runs])
        for version in observations:
            state, reason = self._observed_analysis_state(version, enabled=enabled)
            self._count_analysis(result.analysis, state, reason)
            self._count_analysis(statuses[version["source_id"]].analysis, state, reason)
        result.sources = list(statuses.values())
        counters = result.collection
        counters.sources_total = len(result.sources)
        for row in result.sources:
            if row.status == "queued":
                counters.sources_queued += 1
            elif row.status == "running":
                counters.sources_running += 1
            else:
                counters.sources_done += 1
                if row.status == "completed":
                    counters.sources_completed += 1
                else:
                    counters.sources_failed += 1
            for field in ("new", "updated", "unchanged", "skipped", "warnings"):
                setattr(counters, field, getattr(counters, field) + getattr(row, field))
        result.busy = (job.status in {"queued", "running"} and counters.sources_total > 0) or bool(
            result.analysis.queued + result.analysis.running + result.analysis.pending
        )
        return result

    def _observed_analysis_state(self, version: dict[str, Any], *, enabled: bool) -> tuple[str, str | None]:
        """Classify only the observed hash and explain why pending work cannot run."""
        state = version["job_status"]
        current = version["content_hash"] == version["current_hash"] and version["item_id"] is not None
        available = current and version["duplicate_of_id"] is None
        if available and state == "running":
            return "running", None
        if available and state == "queued":
            if (version["text_length"] or 0) < NEWS_MIN_CONTENT_CHARS:
                return "blocked", "insufficient_text"
            return ("queued", None) if self.config.llm_configured else ("blocked", "missing_llm")
        if state in {"failed", "cancelled"}:
            return "failed", None
        if version["analyzed"]:
            return "completed", None
        if not available or state == "completed":
            return "blocked", "unavailable"
        if (version["text_length"] or 0) < NEWS_MIN_CONTENT_CHARS:
            return "blocked", "insufficient_text"
        if not self.config.llm_configured:
            return "blocked", "missing_llm"
        # Already queued explicit jobs still run while automatic backlog enqueueing is paused.
        if not enabled:
            return "blocked", "paused"
        if version["item_status"] != "pending_analysis":
            return "blocked", "unavailable"
        return "pending", None

    @staticmethod
    def _count_analysis(counters: CollectionAnalysisStatus, state: str, reason: str | None) -> None:
        counters.total += 1
        setattr(counters, state, getattr(counters, state) + 1)
        if reason is not None:
            reasons = counters.blocked_reasons
            setattr(reasons, reason, getattr(reasons, reason) + 1)

    async def get_job(self, job_slug: str) -> JobRow:
        """Read progress without exposing lease ownership or request internals."""
        job = await self.jobs.get_by_slug(job_slug)
        if job is None:
            raise NewsNotFoundError
        source = job.source or (job.item.source if job.item else None)
        return JobRow(
            **{key: getattr(job, key) for key in JobRow.model_fields if key not in {"source_name", "source_slug"}},
            source_name=source.name if source else None,
            source_slug=source.slug if source else None,
        )

    @staticmethod
    def run_row(row: Any) -> RunRow:
        return RunRow(
            **{key: getattr(row, key) for key in RunRow.model_fields if key != "job_slug"},
            job_slug=row.job.slug if row.job else None,
        )

    async def list_runs(
        self, *, page: int, page_size: int, source_slug: str | None = None
    ) -> Paged[RunRow]:
        """Read collection outcomes and bounded safe error summaries."""
        rows, total = await self.runs.list_page(page, page_size, source_slug=source_slug)
        return Paged[RunRow].build([self.run_row(row) for row in rows], total, page, page_size)

    async def list_job_runs(
        self, job_slug: str, *, page: int, page_size: int,
    ) -> Paged[RunRow]:
        """Read source attempts belonging to one job address."""
        job = await self.jobs.get_by_slug(job_slug)
        if job is None:
            raise NewsNotFoundError
        rows, total = await self.runs.list_page(page, page_size, job_id=job.id)
        return Paged[RunRow].build([self.run_row(row) for row in rows], total, page, page_size)

    async def list_job_items(
        self, job_slug: str, *, page: int, page_size: int,
        outcome: str | None = None, warnings_only: bool = False,
        source_slug: str | None = None,
    ) -> Paged[RunItemRow]:
        """Read historical observations without borrowing analysis from a newer item version."""
        job = await self.jobs.get_by_slug(job_slug)
        if job is None:
            raise NewsNotFoundError
        rows, total = await self.runs.list_items(
            job.id, page=page, page_size=page_size, outcome=outcome,
            warnings_only=warnings_only, source_slug=source_slug,
        )
        result = []
        derived = {"source_name", "source_slug", "analysis_status", "analysis_reason", "analysis_job_slug"}
        for row, analysis_job, analyzed in rows:
            status, reason = None, None
            if row.item_id is not None and row.outcome != "skipped":
                status = analysis_job.status if analysis_job else ("completed" if analyzed else "pending")
                if status == "completed" and not analyzed:
                    status = "skipped"
                    reason = {
                        "content_changed": "Версия материала изменилась до завершения анализа.",
                        "missing_or_duplicate": "Материал удалён или отмечен как дубликат.",
                    }.get(
                        (analysis_job.result or {}).get("skipped"),
                        "Задание завершено без сохранённого анализа этой версии.",
                    )
            result.append(RunItemRow(
                **{key: getattr(row, key) for key in RunItemRow.model_fields if key not in derived},
                source_name=row.run.source_name, source_slug=row.run.source_slug,
                analysis_status=status,
                analysis_reason=reason,
                analysis_job_slug=analysis_job.slug if status is not None and analysis_job else None,
            ))
        return Paged[RunItemRow].build(result, total, page, page_size)

    async def get_settings(self) -> SettingsRow:
        """Combine environment defaults and editorial overrides, exposing only LLM readiness."""
        names = (
            "enabled",
            "initial_lookback_days",
            "max_items_per_source",
            "max_excerpt_chars",
            "analysis_batch_size",
            "text_retention_days",
            "history_retention_days",
        )
        defaults = {name: getattr(self.config, name) for name in names}
        supported = {
            key: value for key, value in (await self.settings.get()).items()
            if key in NewsSettingsData.model_fields
        }
        policy = NewsSettingsData.model_validate(
            {**defaults, **supported}
        )
        return SettingsRow(
            **policy.model_dump(),
            llm_configured=self.config.llm_configured,
            llm_provider=self.config.llm_provider,
            llm_model=self.config.llm_model,
        )

    async def update_settings(self, data: SettingsPatch) -> SettingsRow:
        """Validate the effective policy and store only explicitly changed settings."""
        current = await self.get_settings()
        values = data.model_dump(exclude_unset=True)
        try:
            NewsSettingsData.model_validate(
                {
                    **current.model_dump(
                        exclude={"llm_configured", "llm_provider", "llm_model"}
                    ),
                    **values,
                }
            )
        except ValidationError as error:
            raise NewsValidationError from error
        await self.settings.set(values)
        return await self.get_settings()
