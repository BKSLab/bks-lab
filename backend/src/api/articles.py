"""Article endpoints (see docs/api_contract.md)."""

import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response

from src.dependencies.services import ArticleServiceDep
from src.exceptions.content import ArticleNotFoundError
from src.schemas.articles import ArticleDetail, ArticleSummary
from src.schemas.pagination import Paged

logger = logging.getLogger(__name__)

router = APIRouter(tags=["articles"])


@router.get(
    path="/articles",
    summary="List blog articles",
    description=(
        "Paginated list of published articles sorted by published_at desc, "
        "slug asc. Optional filters: category slug and a case-insensitive "
        "substring search over title/excerpt/body. Out-of-range pages return "
        "200 with an empty items list."
    ),
    operation_id="listArticles",
    response_model=Paged[ArticleSummary],
    response_description="Paged list of article summaries.",
    responses={
        200: {"description": "Page of articles."},
        422: {"description": "Invalid query parameters (e.g. q shorter than 2 characters)."},
        500: {"description": "Content storage error."},
    },
)
async def list_articles(
    response: Response,
    service: ArticleServiceDep,
    page: Annotated[int, Query(ge=1, description="Page number (1-based).")] = 1,
    page_size: Annotated[int, Query(ge=1, le=50, description="Items per page.")] = 10,
    category: Annotated[str | None, Query(description="Category slug filter.")] = None,
    q: Annotated[
        str | None, Query(min_length=2, max_length=100, description="Search substring.")
    ] = None,
) -> Paged[ArticleSummary]:
    """List published articles with pagination, category filter and search.

    Args:
        response: Response object for cache headers.
        service: Article service.
        page: Page number.
        page_size: Items per page.
        category: Optional category slug.
        q: Optional search substring (min 2 characters).

    Returns:
        Paged list of article summaries.
    """
    logger.info(
        "GET /articles page=%s page_size=%s category=%s q=%s", page, page_size, category, q
    )
    result = await service.list_articles(
        page=page, page_size=page_size, category=category, query=q
    )
    response.headers["Cache-Control"] = "public, max-age=60"
    return result


@router.get(
    path="/articles/latest",
    summary="Latest articles",
    description="Latest published articles for the home page block.",
    operation_id="listLatestArticles",
    response_model=list[ArticleSummary],
    response_description="Latest article summaries.",
    responses={
        200: {"description": "Latest articles."},
        422: {"description": "Invalid limit."},
        500: {"description": "Content storage error."},
    },
)
async def list_latest_articles(
    response: Response,
    service: ArticleServiceDep,
    limit: Annotated[int, Query(ge=1, le=10, description="Number of articles.")] = 3,
) -> list[ArticleSummary]:
    """Return the latest published articles.

    Args:
        response: Response object for cache headers.
        service: Article service.
        limit: Maximum number of articles (1-10, default 3).

    Returns:
        Latest article summaries.
    """
    logger.info("GET /articles/latest limit=%s", limit)
    result = await service.get_latest(limit=limit)
    response.headers["Cache-Control"] = "public, max-age=60"
    return result


@router.get(
    path="/articles/{slug}",
    summary="Article by slug",
    description="Full article payload including rendered HTML and SEO metadata. "
    "ETag is derived from the content hash.",
    operation_id="getArticle",
    response_model=ArticleDetail,
    response_description="Article detail.",
    responses={
        200: {"description": "Article found."},
        404: {
            "description": "Article not found or is a draft.",
            "content": {"application/json": {"example": {"detail": "Article not found: x"}}},
        },
        500: {"description": "Content storage error."},
    },
)
async def get_article(
    response: Response,
    service: ArticleServiceDep,
    slug: str,
) -> ArticleDetail:
    """Return one published article by slug.

    Args:
        response: Response object for the ETag header.
        service: Article service.
        slug: Article slug.

    Returns:
        Article detail with rendered HTML and SEO metadata.

    Raises:
        HTTPException: 404 when the article is missing or is a draft;
            500 on content storage errors.
    """
    logger.info("GET /articles/%s", slug)
    try:
        result = await service.get_article(slug=slug)
    except ArticleNotFoundError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
    response.headers["ETag"] = f'"{result.content_hash}"'
    return result.payload
