"""Stats endpoints (see docs/api_contract.md)."""

import logging

from fastapi import APIRouter, BackgroundTasks, Request, Response, status

from src.core.limiter import limiter
from src.core.settings import get_settings
from src.dependencies.services import StatsServiceDep
from src.schemas.stats import PageViewRequest
from src.utils.http import get_client_ip

logger = logging.getLogger(__name__)

router = APIRouter(tags=["stats"])


@router.post(
    path="/stats/pageview",
    status_code=status.HTTP_202_ACCEPTED,
    response_class=Response,
    summary="Track a page view",
    description=(
        "Accepts a page view beacon. The insert runs in the background; the "
        "response is returned immediately. Paths outside the route whitelist "
        "and known bots are accepted (202) but not stored, so bots learn "
        "nothing. IP and User-Agent are never persisted — only a daily-salted "
        "visitor hash."
    ),
    operation_id="trackPageView",
    response_description="No body.",
    responses={
        202: {"description": "Accepted."},
        422: {"description": "Missing or invalid request body (e.g. empty or too long path)."},
        429: {
            "description": "Rate limit exceeded (60/minute per IP).",
            "content": {"application/json": {"example": {"detail": "Rate limit exceeded"}}},
        },
    },
)
@limiter.limit(lambda: get_settings().stats.pageview_rate_limit)
async def track_pageview(
    request: Request,
    data: PageViewRequest,
    background_tasks: BackgroundTasks,
    service: StatsServiceDep,
) -> Response:
    """Accept a page view and schedule its storage in the background.

    Args:
        request: Incoming request (client IP and User-Agent source).
        data: Beacon payload (path, optional referrer).
        background_tasks: FastAPI background task runner.
        service: Stats service.

    Returns:
        Empty 202 response.
    """
    view = service.prepare_page_view(
        path=data.path,
        referrer=data.referrer,
        ip=get_client_ip(request),
        user_agent=request.headers.get("user-agent", ""),
    )
    if view is not None:
        background_tasks.add_task(service.save_page_view, view)
    else:
        logger.info("Page view skipped by filters: %s", data.path)
    return Response(status_code=status.HTTP_202_ACCEPTED)
