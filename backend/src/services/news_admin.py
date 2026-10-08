"""Editorial use cases for News Analyzer; no network work runs in API requests."""

from typing import Any

from pydantic import ValidationError

from src.core.news_settings import NewsSettings
from src.exceptions.news import (
    NewsDiscoveryRequiredError,
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
    DiscoverRequest,
    ItemDetail,
    ItemRow,
    JobRow,
    NewsSettingsData,
    QueuedJob,
    RunRow,
    SettingsPatch,
    SettingsRow,
    SourceCreate,
    SourcePatch,
    SourceRow,
)
from src.schemas.pagination import Paged


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
        return SourceRow(
            **{
                key: getattr(row, key)
                for key in SourceRow.model_fields
                if key not in {"topic_ids", "category_ids"}
            },
            topic_ids=[item.id for item in row.topics],
            category_ids=[item.id for item in row.categories],
        )

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
    def item_row(cls, row: Any) -> ItemRow:
        return ItemRow(
            **{
                key: getattr(row, key)
                for key in ItemRow.model_fields
                if key not in {"source_name", "analysis", "decision"}
            },
            source_name=row.source.name,
            analysis=cls.analysis_row(row.analysis) if row.analysis else None,
            decision=DecisionRow.model_validate(row.decision) if row.decision else None,
        )

    async def list_sources(self) -> list[SourceRow]:
        """Read source health and editable configuration without internal cursor state."""
        return [self.source_row(row) for row in await self.sources.list()]

    async def discover(self, data: DiscoverRequest) -> QueuedJob:
        """Queue an SSRF-protected asynchronous preview, never fetch from the request handler."""
        job = await self.jobs.enqueue("discover", payload=data.model_dump())
        return QueuedJob(job_id=job.id, status=job.status)

    async def _validate_taxonomy(self, values: dict) -> None:
        for field, kind in (("topic_ids", "topics"), ("category_ids", "categories")):
            if field in values:
                existing = {row.id for row in await self.catalog.list(kind)}
                if not set(values[field]) <= existing:
                    raise NewsValidationError

    async def _checked_url(
        self, discovery_job_id: int | None, *, url: str, kind: str, config: dict
    ) -> str:
        job = await self.jobs.get(discovery_job_id) if discovery_job_id else None
        if (
            job is None
            or job.kind != "discover"
            or job.status != "completed"
            or not job.result
        ):
            raise NewsDiscoveryRequiredError
        if (
            job.result.get("kind") != kind
            or config != job.payload.get("config", {})
            or url not in {job.payload.get("url"), job.result.get("url")}
        ):
            raise NewsDiscoveryRequiredError
        return job.result.get("url") or url

    async def create_source(self, data: SourceCreate) -> SourceRow:
        """Save only a source matching a successfully completed adapter preview."""
        values = data.model_dump(exclude={"discovery_job_id"})
        values["url"] = await self._checked_url(
            data.discovery_job_id, url=data.url, kind=data.kind, config=data.config
        )
        await self._validate_taxonomy(values)
        return self.source_row(await self.sources.create(values))

    async def update_source(self, source_id: int, data: SourcePatch) -> SourceRow:
        """Require a fresh matching preview for URL, adapter or selector changes."""
        source = await self.sources.get(source_id)
        if source is None:
            raise NewsNotFoundError
        values = data.model_dump(exclude_unset=True, exclude={"discovery_job_id"})
        expected = {key: getattr(source, key) for key in ("url", "kind", "config")}
        effective = {
            **expected,
            **{key: value for key, value in values.items() if key in expected},
        }
        if effective != expected:
            values["url"] = await self._checked_url(data.discovery_job_id, **effective)
        await self._validate_taxonomy(values)
        row = await self.sources.update(source_id, values, expected=expected)
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
        rows, total = await self.items.list_page(
            page=page, page_size=page_size, **filters
        )
        return Paged[ItemRow].build(
            [self.item_row(row) for row in rows], total, page, page_size
        )

    async def get_item(self, item_id: int) -> ItemDetail:
        """Read retained text and complete available editorial history."""
        row = await self.items.get(item_id)
        if row is None:
            raise NewsNotFoundError
        analyses = await self.analyses.list_for_item(item_id)
        decisions = await self.decisions.list_for_item(item_id)
        return ItemDetail(
            **self.item_row(row).model_dump(),
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
        job = await self.jobs.enqueue(
            "analyze",
            item_id=item_id,
            payload={"content_hash": item.content_hash, "force": True},
        )
        return QueuedJob(job_id=job.id, status=job.status)

    async def collect(self, data: CollectRequest) -> QueuedJob:
        """Queue a collection run with an optional existing source scope."""
        if (
            data.source_id is not None
            and await self.sources.get(data.source_id) is None
        ):
            raise NewsNotFoundError
        job = await self.jobs.enqueue("collect", source_id=data.source_id)
        return QueuedJob(job_id=job.id, status=job.status)

    async def get_job(self, job_id: int) -> JobRow:
        """Read progress without exposing lease ownership or request internals."""
        job = await self.jobs.get(job_id)
        if job is None:
            raise NewsNotFoundError
        return JobRow.model_validate(job)

    async def list_runs(
        self, *, page: int, page_size: int, source_id: int | None
    ) -> Paged[RunRow]:
        """Read collection outcomes and bounded safe error summaries."""
        rows, total = await self.runs.list_page(page, page_size, source_id)
        items = [
            RunRow(
                **{
                    key: getattr(row, key)
                    for key in RunRow.model_fields
                    if key != "source_name"
                },
                source_name=row.source.name,
            )
            for row in rows
        ]
        return Paged[RunRow].build(items, total, page, page_size)

    async def get_settings(self) -> SettingsRow:
        """Combine environment defaults and editorial overrides, exposing only LLM readiness."""
        names = (
            "enabled",
            "timezone",
            "schedule",
            "initial_lookback_days",
            "max_items_per_source",
            "max_excerpt_chars",
            "analysis_batch_size",
            "text_retention_days",
            "history_retention_days",
        )
        defaults = {name: getattr(self.config, name) for name in names}
        policy = NewsSettingsData.model_validate(
            {**defaults, **await self.settings.get()}
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
