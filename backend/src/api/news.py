"""Session-protected News Analyzer API; all long operations use the durable queue."""

import logging
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request, Response
from fastapi.routing import APIRoute
from pydantic import AwareDatetime

from src.dependencies.admin import AdminDep, check_admin_origin, require_admin
from src.dependencies.news import NewsAdminServiceDep
from src.schemas.news import (
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
    NewsDecision,
    NewsFormat,
    NewsStatus,
    QueuedJob,
    RunRow,
    SettingsPatch,
    SettingsRow,
    SourceCreate,
    SourcePatch,
    SourceRow,
)
from src.schemas.pagination import Paged

logger = logging.getLogger(__name__)


class NewsRoute(APIRoute):
    """Log bounded operation metadata once per request, excluding editorial input."""

    def get_route_handler(self) -> Callable[[Request], Awaitable[Response]]:
        handler = super().get_route_handler()

        async def logged(request: Request) -> Response:
            logger.info("Starting news operation %s", self.operation_id)
            response = await handler(request)
            logger.info(
                "Completed news operation %s with %s",
                self.operation_id,
                response.status_code,
            )
            return response

        return logged


router = APIRouter(
    prefix="/admin/news",
    tags=["admin-news"],
    route_class=NewsRoute,
    dependencies=[Depends(check_admin_origin), Depends(require_admin)],
    responses={
        401: {"description": "A valid administrator session is required."},
        403: {"description": "Unsafe requests require a trusted Origin."},
        404: {"description": "Requested news record does not exist."},
        409: {
            "description": "Record conflict or matching successful discovery is required."
        },
        422: {"description": "Invalid editorial configuration or request parameters."},
        500: {
            "description": "Internal storage failure; sensitive details are omitted."
        },
    },
)
RowID = Annotated[int, Path(ge=1, description="Positive news record ID.")]
Page = Annotated[int, Query(ge=1, description="One-based page number.")]
PageSize = Annotated[int, Query(ge=1, le=50, description="Maximum rows per page.")]
FilterID = Annotated[
    int | None, Query(ge=1, description="Existing taxonomy or source ID.")
]


@router.get(
    "/sources",
    response_model=list[SourceRow],
    summary="Read news sources",
    description="Read source settings and collection health.",
    operation_id="newsSources",
    response_description="All configured sources.",
)
async def sources(service: NewsAdminServiceDep) -> list[SourceRow]:
    """Read sources without fetching their external URLs."""
    return await service.list_sources()


@router.post(
    "/sources/discover",
    status_code=202,
    response_model=QueuedJob,
    summary="Preview a source",
    description="Queue source detection and a safe preview of up to five materials.",
    operation_id="newsDiscover",
    response_description="Durable discovery job ID.",
)
async def discover(data: DiscoverRequest, service: NewsAdminServiceDep) -> QueuedJob:
    """Queue a checked source preview and return immediately."""
    return await service.discover(data)


@router.post(
    "/sources",
    status_code=201,
    response_model=SourceRow,
    summary="Add a news source",
    description="Save a source after matching successful discovery.",
    operation_id="newsCreateSource",
    response_description="Created source.",
)
async def create_source(data: SourceCreate, service: NewsAdminServiceDep) -> SourceRow:
    """Persist a successfully checked source."""
    return await service.create_source(data)


@router.patch(
    "/sources/{source_id}",
    response_model=SourceRow,
    summary="Edit a news source",
    description="Edit editorial fields or apply newly checked URL and selectors.",
    operation_id="newsUpdateSource",
    response_description="Updated source.",
)
async def update_source(
    source_id: RowID, data: SourcePatch, service: NewsAdminServiceDep
) -> SourceRow:
    """Update a source with discovery enforced for adapter changes."""
    return await service.update_source(source_id, data)


@router.get(
    "/topics",
    response_model=list[CatalogRow],
    summary="Read news topics",
    description="Read the editorial topic catalog.",
    operation_id="newsTopics",
    response_description="All topics.",
)
async def topics(service: NewsAdminServiceDep) -> list[CatalogRow]:
    """Read active and paused topics."""
    return await service.list_catalog("topics")


@router.post(
    "/topics",
    status_code=201,
    response_model=CatalogRow,
    summary="Add a news topic",
    description="Create a topic usable by future classifications.",
    operation_id="newsCreateTopic",
    response_description="Created topic.",
)
async def create_topic(data: CatalogCreate, service: NewsAdminServiceDep) -> CatalogRow:
    """Create an editorial topic."""
    return await service.create_catalog("topics", data)


@router.patch(
    "/topics/{topic_id}",
    response_model=CatalogRow,
    summary="Edit a news topic",
    description="Update a label or pause the topic without deleting history.",
    operation_id="newsUpdateTopic",
    response_description="Updated topic.",
)
async def update_topic(
    topic_id: RowID, data: CatalogPatch, service: NewsAdminServiceDep
) -> CatalogRow:
    """Edit an existing topic."""
    return await service.update_catalog("topics", topic_id, data)


@router.get(
    "/categories",
    response_model=list[CatalogRow],
    summary="Read news categories",
    description="Read the editorial category catalog.",
    operation_id="newsCategories",
    response_description="All categories.",
)
async def categories(service: NewsAdminServiceDep) -> list[CatalogRow]:
    """Read active and paused categories."""
    return await service.list_catalog("categories")


@router.post(
    "/categories",
    status_code=201,
    response_model=CatalogRow,
    summary="Add a news category",
    description="Create a category usable by future classifications.",
    operation_id="newsCreateCategory",
    response_description="Created category.",
)
async def create_category(
    data: CatalogCreate, service: NewsAdminServiceDep
) -> CatalogRow:
    """Create an editorial category."""
    return await service.create_catalog("categories", data)


@router.patch(
    "/categories/{category_id}",
    response_model=CatalogRow,
    summary="Edit a news category",
    description="Update a category without rewriting classification history.",
    operation_id="newsUpdateCategory",
    response_description="Updated category.",
)
async def update_category(
    category_id: RowID, data: CatalogPatch, service: NewsAdminServiceDep
) -> CatalogRow:
    """Edit an existing category."""
    return await service.update_catalog("categories", category_id, data)


@router.get(
    "/items",
    response_model=Paged[ItemRow],
    summary="Read collected news",
    description="Filter and rank current analyses; unfiltered lists include pending items.",
    operation_id="newsItems",
    response_description="Paged editorial queue.",
)
async def items(
    service: NewsAdminServiceDep,
    page: Page = 1,
    page_size: PageSize = 20,
    source_id: FilterID = None,
    category_id: FilterID = None,
    topic_id: FilterID = None,
    format: Annotated[
        NewsFormat | None, Query(description="Recommended editorial format.")
    ] = None,
    status: Annotated[
        NewsStatus | None, Query(description="Current analysis state.")
    ] = None,
    decision: Annotated[
        NewsDecision | None, Query(description="Latest editorial decision.")
    ] = None,
    min_score: Annotated[
        float | None, Query(ge=0, le=100, description="Minimum weighted score.")
    ] = None,
    date_from: Annotated[
        AwareDatetime | None, Query(description="Earliest first observation, ISO 8601.")
    ] = None,
    date_to: Annotated[
        AwareDatetime | None, Query(description="Latest first observation, ISO 8601.")
    ] = None,
) -> Paged[ItemRow]:
    """Read a bounded page with optional editorial filters."""
    return await service.list_items(
        page=page,
        page_size=page_size,
        source_id=source_id,
        category_id=category_id,
        topic_id=topic_id,
        format=format,
        status=status,
        decision=decision,
        min_score=min_score,
        date_from=date_from,
        date_to=date_to,
    )


@router.get(
    "/items/{item_id}",
    response_model=ItemDetail,
    summary="Read a collected item",
    description="Read retained source text, analyses and editorial decisions.",
    operation_id="newsItem",
    response_description="Collected material and history.",
)
async def item(item_id: RowID, service: NewsAdminServiceDep) -> ItemDetail:
    """Read collected content independently of published Markdown."""
    return await service.get_item(item_id)


@router.post(
    "/items/{item_id}/decision",
    response_model=DecisionRow,
    summary="Record an editorial decision",
    description="Append a disposition attributed to the authenticated administrator.",
    operation_id="newsDecision",
    response_description="Saved editorial decision.",
)
async def decide(
    item_id: RowID, data: DecisionRequest, admin: AdminDep, service: NewsAdminServiceDep
) -> DecisionRow:
    """Record an editor decision without publishing content."""
    return await service.decide(item_id, data, admin.username)


@router.post(
    "/items/{item_id}/reanalyze",
    status_code=202,
    response_model=QueuedJob,
    summary="Reanalyze a collected item",
    description="Queue an explicit model attempt for the current content version.",
    operation_id="newsReanalyze",
    response_description="Durable analysis job ID.",
)
async def reanalyze(item_id: RowID, service: NewsAdminServiceDep) -> QueuedJob:
    """Queue analysis without holding the HTTP request open."""
    return await service.reanalyze(item_id)


@router.post(
    "/jobs/collect",
    status_code=202,
    response_model=QueuedJob,
    summary="Collect news now",
    description="Queue all active sources or one source for manual collection.",
    operation_id="newsCollect",
    response_description="Durable collection job ID.",
)
async def collect(data: CollectRequest, service: NewsAdminServiceDep) -> QueuedJob:
    """Queue a collection run without fetching within the API process."""
    return await service.collect(data)


@router.get(
    "/jobs/{job_id}",
    response_model=JobRow,
    summary="Read a news job",
    description="Read durable state, counters and safe discovery results.",
    operation_id="newsJob",
    response_description="Current job state.",
)
async def job(job_id: RowID, service: NewsAdminServiceDep) -> JobRow:
    """Read progress and a completed source preview."""
    return await service.get_job(job_id)


@router.get(
    "/runs",
    response_model=Paged[RunRow],
    summary="Read collection history",
    description="Read per-source attempts and ingestion counters.",
    operation_id="newsRuns",
    response_description="Paged collection history.",
)
async def runs(
    service: NewsAdminServiceDep,
    page: Page = 1,
    page_size: PageSize = 20,
    source_id: FilterID = None,
) -> Paged[RunRow]:
    """Read collection outcomes and safe failure summaries."""
    return await service.list_runs(page=page, page_size=page_size, source_id=source_id)


@router.get(
    "/settings",
    response_model=SettingsRow,
    summary="Read news settings",
    description="Read editorial policy, schedule and safe provider readiness.",
    operation_id="newsSettings",
    response_description="Effective settings without provider credentials.",
)
async def settings(service: NewsAdminServiceDep) -> SettingsRow:
    """Read runtime defaults combined with saved overrides."""
    return await service.get_settings()


@router.patch(
    "/settings",
    response_model=SettingsRow,
    summary="Update news settings",
    description="Validate and save editorial policy, ranking weights and schedule.",
    operation_id="newsUpdateSettings",
    response_description="Updated effective settings.",
)
async def update_settings(
    data: SettingsPatch, service: NewsAdminServiceDep
) -> SettingsRow:
    """Persist validated settings for the independent scheduler."""
    return await service.update_settings(data)
