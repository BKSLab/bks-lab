"""Note endpoints (see docs/api_contract.md)."""

import logging
from typing import Annotated

from fastapi import APIRouter, Query, Response

from src.dependencies.services import NoteServiceDep
from src.schemas.notes import Note
from src.schemas.pagination import Paged

logger = logging.getLogger(__name__)

router = APIRouter(tags=["notes"])


@router.get(
    path="/notes",
    summary="Notes feed",
    description=(
        "Paginated feed of published notes sorted by published_at desc, "
        "slug asc. Notes have no dedicated pages; the feed is anchored "
        "with #note-<slug>."
    ),
    operation_id="listNotes",
    response_model=Paged[Note],
    response_description="Paged list of notes.",
    responses={
        200: {"description": "Page of notes."},
        422: {"description": "Invalid pagination parameters."},
        500: {"description": "Content storage error."},
    },
)
async def list_notes(
    response: Response,
    service: NoteServiceDep,
    page: Annotated[int, Query(ge=1, description="Page number (1-based).")] = 1,
    page_size: Annotated[int, Query(ge=1, le=50, description="Items per page.")] = 20,
) -> Paged[Note]:
    """List published notes with pagination.

    Args:
        response: Response object for cache headers.
        service: Note service.
        page: Page number.
        page_size: Items per page (default 20; notes are short).

    Returns:
        Paged list of notes.
    """
    logger.info("GET /notes page=%s page_size=%s", page, page_size)
    result = await service.list_notes(page=page, page_size=page_size)
    response.headers["Cache-Control"] = "public, max-age=60"
    return result


@router.get(
    path="/notes/latest",
    summary="Latest notes",
    description="Latest published notes for the home page block and the blog sidebar.",
    operation_id="listLatestNotes",
    response_model=list[Note],
    response_description="Latest notes.",
    responses={
        200: {"description": "Latest notes."},
        422: {"description": "Invalid limit."},
        500: {"description": "Content storage error."},
    },
)
async def list_latest_notes(
    response: Response,
    service: NoteServiceDep,
    limit: Annotated[int, Query(ge=1, le=10, description="Number of notes.")] = 3,
) -> list[Note]:
    """Return the latest published notes.

    Args:
        response: Response object for cache headers.
        service: Note service.
        limit: Maximum number of notes (1-10, default 3).

    Returns:
        Latest notes.
    """
    logger.info("GET /notes/latest limit=%s", limit)
    result = await service.get_latest(limit=limit)
    response.headers["Cache-Control"] = "public, max-age=60"
    return result
