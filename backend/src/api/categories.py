"""Category endpoints (see docs/api_contract.md)."""

import logging

from fastapi import APIRouter, Response

from src.dependencies.services import CategoryServiceDep
from src.schemas.categories import Category

logger = logging.getLogger(__name__)

router = APIRouter(tags=["categories"])


@router.get(
    path="/categories",
    summary="List blog categories",
    description=(
        "The fixed category set (design spec section 11) with published-article "
        "counts. Categories with zero articles are included for blog filters."
    ),
    operation_id="listCategories",
    response_model=list[Category],
    response_description="Category list.",
    responses={
        200: {"description": "Category list."},
        500: {"description": "Content storage error."},
    },
)
async def list_categories(
    response: Response,
    service: CategoryServiceDep,
) -> list[Category]:
    """List all blog categories with article counts.

    Args:
        response: Response object for cache headers.
        service: Category service.

    Returns:
        All fixed categories with published-article counts.
    """
    logger.info("GET /categories")
    result = await service.list_categories()
    response.headers["Cache-Control"] = "public, max-age=60"
    return result
