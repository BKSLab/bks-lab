"""Project endpoints (see docs/api_contract.md)."""

import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response

from src.dependencies.services import ProjectServiceDep
from src.exceptions.content import ProjectNotFoundError
from src.schemas.projects import ProjectDetail, ProjectSummary

logger = logging.getLogger(__name__)

router = APIRouter(tags=["projects"])


@router.get(
    path="/projects",
    summary="List projects",
    description=(
        "Published projects sorted by order asc, slug asc. "
        "`featured=true` selects the home page block."
    ),
    operation_id="listProjects",
    response_model=list[ProjectSummary],
    response_description="Project summaries.",
    responses={
        200: {"description": "Project list."},
        422: {"description": "Invalid query parameters."},
        500: {"description": "Content storage error."},
    },
)
async def list_projects(
    response: Response,
    service: ProjectServiceDep,
    featured: Annotated[
        bool | None, Query(description="Filter by the featured flag.")
    ] = None,
) -> list[ProjectSummary]:
    """List published projects, optionally filtered by the featured flag.

    Args:
        response: Response object for cache headers.
        service: Project service.
        featured: Optional featured filter.

    Returns:
        Project summaries.
    """
    logger.info("GET /projects featured=%s", featured)
    result = await service.list_projects(featured=featured)
    response.headers["Cache-Control"] = "public, max-age=60"
    return result


@router.get(
    path="/projects/{slug}",
    summary="Project by slug",
    description="Full project payload including rendered HTML and SEO metadata. "
    "ETag is derived from the content hash.",
    operation_id="getProject",
    response_model=ProjectDetail,
    response_description="Project detail.",
    responses={
        200: {"description": "Project found."},
        404: {
            "description": "Project not found or is a draft.",
            "content": {"application/json": {"example": {"detail": "Project not found: x"}}},
        },
        500: {"description": "Content storage error."},
    },
)
async def get_project(
    response: Response,
    service: ProjectServiceDep,
    slug: str,
) -> ProjectDetail:
    """Return one published project by slug.

    Args:
        response: Response object for the ETag header.
        service: Project service.
        slug: Project slug.

    Returns:
        Project detail with rendered HTML and SEO metadata.

    Raises:
        HTTPException: 404 when the project is missing or is a draft.
    """
    logger.info("GET /projects/%s", slug)
    try:
        result = await service.get_project(slug=slug)
    except ProjectNotFoundError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
    response.headers["ETag"] = f'"{result.content_hash}"'
    return result.payload
