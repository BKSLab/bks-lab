"""Session-protected News Analyzer API; all long operations use the durable queue."""

import logging
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request, Response
from fastapi.routing import APIRoute
from pydantic import AwareDatetime

from src.dependencies.admin import AdminDep, check_admin_origin, require_admin
from src.dependencies.news import NewsAdminServiceDep
from src.dependencies.news_notes import NewsNoteServiceDep
from src.schemas.news_notes import NoteSettingsPatch, NoteSettingsRow, NoteQueuePatch, NoteQueueRow, QueueStatus
from src.schemas.news import (
    CatalogCreate,
    CatalogPatch,
    CatalogRow,
    CollectRequest,
    DecisionRequest,
    DecisionRow,
    ItemDetail,
    ItemRow,
    JobRow,
    NewsDecision,
    NewsFormat,
    NewsStatus,
    NewsSlug,
    QueuedJob,
    RunRow,
    RunItemRow,
    RunOutcome,
    SettingsPatch,
    SettingsRow,
    SourcePatch,
    SourceRow,
)
from src.schemas.pagination import Paged
from src.schemas.news_collection_status import CollectionStatus

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
            "description": "Concurrent record conflict."
        },
        422: {"description": "Invalid editorial configuration or request parameters."},
        500: {
            "description": "Internal storage failure; sensitive details are omitted."
        },
    },
)
RowID = Annotated[int, Path(ge=1, description="Positive news record ID.")]
Slug = Annotated[NewsSlug, Path(description="Stable readable news address.")]
FilterSlug = Annotated[NewsSlug | None, Query(description="Stable source address.")]
Page = Annotated[int, Query(ge=1, description="One-based page number.")]
PageSize = Annotated[int, Query(ge=1, le=50, description="Maximum rows per page.")]
FilterID = Annotated[
    int | None, Query(ge=1, description="Existing taxonomy ID.")
]


@router.get(
    "/note-settings", response_model=NoteSettingsRow, summary="Read automatic note settings",
    description="Read publication settings, activation boundary and queue counts.",
    operation_id="newsNoteSettings", response_description="Automatic note configuration and counts.",
)
async def note_settings(service: NewsNoteServiceDep) -> NoteSettingsRow:
    """Read automatic publication state without calling external services."""
    return await service.get_settings()


@router.patch(
    "/note-settings", response_model=NoteSettingsRow, summary="Edit automatic note settings",
    description="Pause/resume publication or set its interval and maximum age; the first enablement establishes the permanent admission boundary.",
    operation_id="newsUpdateNoteSettings", response_description="Updated automatic note settings.",
)
async def update_note_settings(data: NoteSettingsPatch, service: NewsNoteServiceDep) -> NoteSettingsRow:
    """Set publication policy without retroactive admission of existing material."""
    return await service.update_settings(data)


@router.get(
    "/note-queue", response_model=Paged[NoteQueueRow], summary="Read automatic note queue",
    description="Read draft/publication dispositions with exact source snapshots and content editor IDs.",
    operation_id="newsNoteQueue", response_description="One disposition page.",
)
async def note_queue(
    service: NewsNoteServiceDep,
    status: Annotated[QueueStatus, Query(description="Queue disposition.")] = "queued",
    page: Page = 1, page_size: PageSize = 20,
) -> Paged[NoteQueueRow]:
    """Read queue text from live content without overwriting editor changes."""
    return await service.list_queue(status=status, page=page, page_size=page_size)


@router.patch(
    "/note-queue/{note_slug}", response_model=NoteQueueRow, summary="Edit an automatic note draft",
    description="Edit a bounded draft title/text, exclude it or return an excluded draft to the queue. Published notes use the content editor.",
    operation_id="newsUpdateNoteQueue", response_description="Updated queue row.",
)
async def update_note_queue(note_slug: Slug, data: NoteQueuePatch, service: NewsNoteServiceDep) -> NoteQueueRow:
    """Save draft changes with a revision or change the queue disposition."""
    return await service.update_queue(note_slug, data)


@router.get(
    "/sources",
    response_model=list[SourceRow],
    summary="Read news sources",
    description="Read source settings and collection health.",
    operation_id="newsSources",
    response_description="Verified source profiles with collection preferences.",
)
async def sources(service: NewsAdminServiceDep) -> list[SourceRow]:
    """Read sources without fetching their external URLs."""
    return await service.list_sources()


@router.get(
    "/sources/{source_slug}",
    response_model=SourceRow,
    summary="Read a news source",
    description="Read one source's configuration and collection health by its stable address.",
    operation_id="newsSource",
    response_description="Source configuration and health.",
)
async def source(source_slug: Slug, service: NewsAdminServiceDep) -> SourceRow:
    """Read a configured source without requesting any external resource."""
    return await service.get_source(source_slug)


@router.patch(
    "/sources/{source_slug}",
    response_model=SourceRow,
    summary="Edit a news source",
    description="Change only source enablement and its collection calendar in Europe/Samara.",
    operation_id="newsUpdateSource",
    response_description="Updated source.",
)
async def update_source(
    source_slug: Slug, data: SourcePatch, service: NewsAdminServiceDep
) -> SourceRow:
    """Update enablement or the source calendar without modifying its code-owned profile."""
    return await service.update_source(source_slug, data)


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
    source_slug: FilterSlug = None,
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
        source_slug=source_slug,
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
    "/collection-status",
    response_model=CollectionStatus,
    summary="Read durable collection and analysis progress",
    description="Restore source and overall progress for an explicit collection or the most relevant durable job.",
    operation_id="newsCollectionStatus",
    response_description="Safe collection targets and exact-version analysis counters.",
)
async def collection_status(
    service: NewsAdminServiceDep,
    job_slug: Annotated[NewsSlug | None, Query(description="Optional stable collection job address.")] = None,
) -> CollectionStatus:
    """Read saved progress without keeping a database connection open between polls."""
    return await service.collection_status(job_slug)


@router.get(
    "/jobs/{job_slug}",
    response_model=JobRow,
    summary="Read a news job",
    description="Read durable state, counters and safe discovery results.",
    operation_id="newsJob",
    response_description="Current job state.",
)
async def job(job_slug: Slug, service: NewsAdminServiceDep) -> JobRow:
    """Read progress and a completed source preview."""
    return await service.get_job(job_slug)


@router.get(
    "/jobs/{job_slug}/runs",
    response_model=Paged[RunRow],
    summary="Read source attempts for a job",
    description="Read saved source snapshots, collection parameters and counters for one job.",
    operation_id="newsJobRuns",
    response_description="Paged source run report.",
)
async def job_runs(
    job_slug: Slug, service: NewsAdminServiceDep,
    page: Page = 1, page_size: PageSize = 20,
) -> Paged[RunRow]:
    """Read one job's bounded collection attempt history."""
    return await service.list_job_runs(job_slug, page=page, page_size=page_size)


@router.get(
    "/jobs/{job_slug}/items",
    response_model=Paged[RunItemRow],
    summary="Read candidate observations for a job",
    description="Read historical ingestion outcomes and exact-version analysis state, with bounded filters.",
    operation_id="newsJobItems",
    response_description="Paged candidate observations.",
)
async def job_items(
    job_slug: Slug, service: NewsAdminServiceDep,
    page: Page = 1, page_size: PageSize = 20,
    outcome: Annotated[RunOutcome | None, Query(description="Observed ingestion outcome.")] = None,
    warnings_only: Annotated[bool, Query(description="Return only observations carrying a warning.")] = False,
    source_slug: FilterSlug = None,
) -> Paged[RunItemRow]:
    """Read candidate details independently of the mutable current material."""
    return await service.list_job_items(
        job_slug, page=page, page_size=page_size, outcome=outcome,
        warnings_only=warnings_only, source_slug=source_slug,
    )


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
    source_slug: FilterSlug = None,
) -> Paged[RunRow]:
    """Read collection outcomes and safe failure summaries."""
    return await service.list_runs(page=page, page_size=page_size, source_slug=source_slug)


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
