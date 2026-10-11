"""Protected, read-only Admin API and same-origin session authentication."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Path, Query, Request, Response, UploadFile

from src.core.limiter import limiter
from src.core.settings import get_settings
from src.dependencies.admin import (
    AdminDep, COOKIE_NAME, check_admin_origin, clear_session_cookie, require_admin,
    set_session_cookie,
)
from src.dependencies.services import (
    AdminAuthServiceDep, AdminContentServiceDep, AdminStatsServiceDep,
    ContentAdminServiceDep, MediaServiceDep, SubscriberServiceDep,
)
from src.schemas.admin import (
    AdminIdentity, ContentCreate, ContentItemDetail, ContentItemFull, ContentItemRow,
    ContentPatch, ContentPreviewRequest, ContentPreviewResponse, ContentRevisionDetail,
    ContentRevisionRow, ContentStatus, ContentStatusChange, ContentType, LoginRequest,
    LoginResponse, MediaFileRow, Metric, Overview, PageStatsRow, Period, ReferrerRow,
    SubscriberRow, TimeseriesPoint,
)
from src.schemas.pagination import Paged

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(check_admin_origin)])
protected = APIRouter(dependencies=[Depends(require_admin)], responses={
    401: {"description": "Missing or expired admin session."},
    500: {"description": "Storage is temporarily unavailable."},
})

Page = Annotated[int, Query(ge=1, description="Page number, starting at one.")]
PageSize = Annotated[int, Query(ge=1, le=50, description="Rows per page, maximum fifty.")]
PeriodQuery = Annotated[Period, Query(description="UTC calendar days including today.")]


@router.post(
    "/auth/login", response_model=LoginResponse, summary="Create an admin session",
    description="Compare configured credentials and issue an opaque httpOnly cookie.",
    operation_id="adminLogin", response_description="Session created; token only in Set-Cookie.",
    responses={401: {"description": "Invalid credentials."}, 403: {"description": "Origin not allowed."},
               429: {"description": "Five attempts per minute per IP."}, 500: {"description": "Session storage unavailable."}},
)
@limiter.limit("5/minute")
async def login(
    request: Request, response: Response, data: LoginRequest, service: AdminAuthServiceDep,
) -> LoginResponse:
    """Create a fresh session after a same-origin credential check."""
    grant = await service.login(data.username, data.password.get_secret_value(), request.cookies.get(COOKIE_NAME))
    set_session_cookie(response, grant.token)
    return LoginResponse()


@protected.post(
    "/auth/logout", status_code=204, response_class=Response,
    summary="Revoke an admin session", description="Delete the current server-side session and its cookie.",
    operation_id="adminLogout", response_description="Session revoked; no body.",
    responses={403: {"description": "Origin not allowed."}},
)
async def logout(admin: AdminDep, service: AdminAuthServiceDep) -> Response:
    """Revoke the authenticated session and clear its scoped cookie."""
    await service.logout(admin)
    response = Response(status_code=204)
    clear_session_cookie(response)
    return response


@protected.get(
    "/auth/me", response_model=AdminIdentity, summary="Check an admin session",
    description="Validate and renew the session; expose only the configured username.",
    operation_id="adminMe", response_description="Authenticated administrator.",
)
async def me(admin: AdminDep) -> AdminIdentity:
    """Return the authenticated identity, never the token or its digest."""
    return AdminIdentity(username=admin.username)


@protected.get(
    "/overview", response_model=Overview, summary="Read dashboard counters",
    description="UTC views today, seven/thirty days, daily uniques and top paths/referrers.",
    operation_id="adminOverview", response_description="Live aggregated visit statistics.",
)
async def overview(service: AdminStatsServiceDep) -> Overview:
    """Read the dashboard overview."""
    return await service.overview()


@protected.get(
    "/stats/timeseries", response_model=list[TimeseriesPoint], summary="Read daily statistics",
    description="Return every UTC date in the period, including zero-valued days.",
    operation_id="adminStatsTimeseries", response_description="Chronological daily values.",
)
async def timeseries(
    service: AdminStatsServiceDep,
    metric: Annotated[Metric, Query(description="Views or daily uniques.")] = "views",
    period: PeriodQuery = "30d",
) -> list[TimeseriesPoint]:
    """Read a complete daily series for the chosen metric."""
    return await service.timeseries(metric=metric, period=period)


@protected.get(
    "/stats/pages", response_model=Paged[PageStatsRow], summary="Read page statistics",
    description="Group page paths and note anchors, ordered by views descending.",
    operation_id="adminStatsPages", response_description="Paged path and note visit counts.",
)
async def pages(
    service: AdminStatsServiceDep, period: PeriodQuery = "30d", page: Page = 1, page_size: PageSize = 20,
) -> Paged[PageStatsRow]:
    """Read page counts and summed daily uniques."""
    return await service.pages(period=period, page=page, page_size=page_size)


@protected.get(
    "/stats/referrers", response_model=list[ReferrerRow], summary="Read referrer statistics",
    description="Top fifty external referrer domains, excluding missing domains.",
    operation_id="adminStatsReferrers", response_description="Domains by descending visits.",
)
async def referrers(service: AdminStatsServiceDep, period: PeriodQuery = "30d") -> list[ReferrerRow]:
    """Read the leading referrer domains."""
    return await service.referrers(period)


@protected.get(
    "/content", response_model=Paged[ContentItemRow], summary="Read the content registry",
    description="Search the content storage, including draft and archived materials.",
    operation_id="adminContent", response_description="Filtered materials with thirty-day visits.",
)
async def content(
    service: AdminContentServiceDep,
    content_type: Annotated[ContentType | None, Query(alias="type", description="Content type.")] = None,
    status: Annotated[ContentStatus | None, Query(description="Projection status.")] = None,
    q: Annotated[str | None, Query(max_length=100, description="Literal title substring, case-insensitive.")] = None,
    page: Page = 1, page_size: PageSize = 20,
) -> Paged[ContentItemRow]:
    """Read stored materials with validated filters and bounded pagination."""
    return await service.get_page(content_type=content_type, status=status, query=q, page=page, page_size=page_size)


@protected.post(
    "/content/images", status_code=201, response_model=MediaFileRow, summary="Upload an image",
    description="Accept a JPEG/PNG/WebP file, convert it to WebP (downscaled to the configured width) and register it for the editor insert dialog.",
    operation_id="adminContentImageUpload", response_description="Stored image with its public /uploads path.",
    responses={403: {"description": "Origin not allowed."}, 413: {"description": "Image exceeds the size limit."},
               422: {"description": "Not a supported image or unknown section."}},
)
async def content_image_upload(
    service: MediaServiceDep,
    file: Annotated[UploadFile, File(description="JPEG, PNG or WebP image.")],
    section: Annotated[str, Form(description="Storage section: articles | notes | projects | covers | shared.")] = "shared",
) -> MediaFileRow:
    """Convert and store one uploaded image."""
    data = await file.read(get_settings().media.max_bytes + 1)
    media = await service.save_upload(
        original_name=file.filename or "image", data=data, section=section
    )
    return MediaFileRow.model_validate(media)


@protected.get(
    "/content/images", response_model=list[MediaFileRow], summary="List uploaded images",
    description="Uploaded images, newest first, for the editor insert dialog.",
    operation_id="adminContentImages", response_description="Image library rows.",
)
async def content_images(service: MediaServiceDep) -> list[MediaFileRow]:
    """List the image library."""
    rows = await service.list_images()
    return [MediaFileRow.model_validate(row) for row in rows]


@protected.get(
    "/content/{item_id}", response_model=ContentItemDetail, summary="Read material details",
    description="Stored metadata, the source Markdown for the editor and the thirty-day visit series.",
    operation_id="adminContentDetail", response_description="Material metadata, Markdown body and visit series.",
    responses={404: {"description": "Material does not exist."}},
)
async def content_detail(
    service: AdminContentServiceDep, item_id: Annotated[int, Path(ge=1, description="Content item ID.")],
) -> ContentItemDetail:
    """Read one material, including the Markdown body for the editor."""
    return await service.get_detail(item_id)


@protected.post(
    "/content", status_code=201, response_model=ContentItemFull, summary="Create a material",
    description="Create an article, note or project (draft by default); the first revision is recorded.",
    operation_id="adminContentCreate", response_description="Created material with derived fields.",
    responses={403: {"description": "Origin not allowed."}, 409: {"description": "Slug already exists for this type."},
               422: {"description": "Type-specific validation failed."}},
)
async def content_create(service: ContentAdminServiceDep, data: ContentCreate) -> ContentItemFull:
    """Create a material and its first revision in one transaction."""
    return await service.create_item(data)


@protected.post(
    "/content/preview", response_model=ContentPreviewResponse, summary="Render a Markdown preview",
    description="Render the editor body to HTML with the same pipeline used on save, for the live preview. Nothing is stored, no revalidation fires.",
    operation_id="adminContentPreview", response_description="Rendered HTML (unsanitized, like stored content_html).",
    responses={403: {"description": "Origin not allowed."}, 422: {"description": "Input validation failed."}},
)
async def content_preview(
    service: ContentAdminServiceDep, data: ContentPreviewRequest,
) -> ContentPreviewResponse:
    """Render Markdown for the live editor preview without touching storage."""
    return ContentPreviewResponse(html=service.render_preview(data.content_markdown))


@protected.patch(
    "/content/{item_id}", response_model=ContentItemFull, summary="Save material edits",
    description="Apply a partial edit; the merged state is validated per content type and a revision is recorded.",
    operation_id="adminContentUpdate", response_description="Updated material with derived fields.",
    responses={403: {"description": "Origin not allowed."}, 404: {"description": "Material does not exist."},
               422: {"description": "Type-specific validation failed."}},
)
async def content_update(
    service: ContentAdminServiceDep,
    data: ContentPatch,
    item_id: Annotated[int, Path(ge=1, description="Content item ID.")],
) -> ContentItemFull:
    """Save edits and record a revision in one transaction."""
    return await service.update_item(item_id, data)


@protected.delete(
    "/content/{item_id}", status_code=204, response_class=Response, summary="Delete a material",
    description="Delete the material; its revisions are removed by cascade.",
    operation_id="adminContentDelete", response_description="Deleted; no body.",
    responses={403: {"description": "Origin not allowed."}, 404: {"description": "Material does not exist."}},
)
async def content_delete(
    service: ContentAdminServiceDep, item_id: Annotated[int, Path(ge=1, description="Content item ID.")],
) -> Response:
    """Delete one material."""
    await service.delete_item(item_id)
    return Response(status_code=204)


@protected.post(
    "/content/{item_id}/status", response_model=ContentItemFull, summary="Change material status",
    description="Transition the status (draft | active | archived); archived is valid for projects only. A revision is recorded.",
    operation_id="adminContentSetStatus", response_description="Material with the new status.",
    responses={403: {"description": "Origin not allowed."}, 404: {"description": "Material does not exist."},
               422: {"description": "Archived is allowed for projects only."}},
)
async def content_set_status(
    service: ContentAdminServiceDep,
    data: ContentStatusChange,
    item_id: Annotated[int, Path(ge=1, description="Content item ID.")],
) -> ContentItemFull:
    """Change the publication status and record a revision."""
    return await service.set_status(item_id, data.status)


@protected.get(
    "/content/{item_id}/revisions", response_model=list[ContentRevisionRow], summary="List material versions",
    description="Version metadata (revision number, word count, saved at), newest first.",
    operation_id="adminContentRevisions", response_description="Version list.",
    responses={404: {"description": "Material does not exist."}},
)
async def content_revisions(
    service: ContentAdminServiceDep, item_id: Annotated[int, Path(ge=1, description="Content item ID.")],
) -> list[ContentRevisionRow]:
    """List the version history of one material."""
    return await service.list_revisions(item_id)


@protected.get(
    "/content/{item_id}/revisions/{revision_no}", response_model=ContentRevisionDetail, summary="Read one version",
    description="Full snapshot of one saved version, including the Markdown body.",
    operation_id="adminContentRevision", response_description="Version snapshot.",
    responses={404: {"description": "Material or version does not exist."}},
)
async def content_revision(
    service: ContentAdminServiceDep,
    item_id: Annotated[int, Path(ge=1, description="Content item ID.")],
    revision_no: Annotated[int, Path(ge=1, description="Revision number within the material.")],
) -> ContentRevisionDetail:
    """Read one version snapshot."""
    return await service.get_revision(item_id, revision_no)


@protected.post(
    "/content/{item_id}/revisions/{revision_no}/restore", response_model=ContentItemFull,
    summary="Restore a version",
    description="Copy the chosen snapshot back into the material and record it as a new revision; history is never rewritten.",
    operation_id="adminContentRestore", response_description="Material restored to the chosen version.",
    responses={403: {"description": "Origin not allowed."}, 404: {"description": "Material or version does not exist."}},
)
async def content_restore(
    service: ContentAdminServiceDep,
    item_id: Annotated[int, Path(ge=1, description="Content item ID.")],
    revision_no: Annotated[int, Path(ge=1, description="Revision number within the material.")],
) -> ContentItemFull:
    """Restore one version as a new revision."""
    return await service.restore_revision(item_id, revision_no)


@protected.get(
    "/subscribers", response_model=Paged[SubscriberRow], summary="Read subscribers",
    description="List subscribers by first subscription time, newest first.",
    operation_id="adminSubscribers", response_description="Paged subscriber email and UTC timestamp.",
)
async def subscribers(
    service: SubscriberServiceDep, page: Page = 1, page_size: PageSize = 20,
) -> Paged[SubscriberRow]:
    """Read the subscriber registry; the API provides no mutation route."""
    return await service.get_page(page=page, page_size=page_size)


router.include_router(protected)
