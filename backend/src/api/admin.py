"""Protected, read-only Admin API and same-origin session authentication."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request, Response

from src.core.limiter import limiter
from src.dependencies.admin import (
    AdminDep, COOKIE_NAME, check_admin_origin, clear_session_cookie, require_admin,
    set_session_cookie,
)
from src.dependencies.services import (
    AdminAuthServiceDep, AdminContentServiceDep, AdminStatsServiceDep, SubscriberServiceDep,
)
from src.schemas.admin import (
    AdminIdentity, ContentItemDetail, ContentItemRow, ContentStatus, ContentType,
    LoginRequest, LoginResponse, Metric, Overview, PageStatsRow, Period,
    ReferrerRow, SubscriberRow, TimeseriesPoint,
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
    description="Search the synchronized Markdown projection, including draft and archived materials.",
    operation_id="adminContent", response_description="Filtered materials with thirty-day visits.",
)
async def content(
    service: AdminContentServiceDep,
    content_type: Annotated[ContentType | None, Query(alias="type", description="Content type.")] = None,
    status: Annotated[ContentStatus | None, Query(description="Projection status.")] = None,
    q: Annotated[str | None, Query(max_length=100, description="Literal title substring, case-insensitive.")] = None,
    page: Page = 1, page_size: PageSize = 20,
) -> Paged[ContentItemRow]:
    """Read projected materials with validated filters and bounded pagination."""
    return await service.get_page(content_type=content_type, status=status, query=q, page=page, page_size=page_size)


@protected.get(
    "/content/{item_id}", response_model=ContentItemDetail, summary="Read material details",
    description="Projection metadata and thirty-day visit series; content stays editable only in git.",
    operation_id="adminContentDetail", response_description="Material metadata and visit series.",
    responses={404: {"description": "Material does not exist."}},
)
async def content_detail(
    service: AdminContentServiceDep, item_id: Annotated[int, Path(ge=1, description="Projection row ID.")],
) -> ContentItemDetail:
    """Read one material without exposing any editing endpoint."""
    return await service.get_detail(item_id)


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
