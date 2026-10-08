"""Unit tests for ArticleService with a mocked repository."""

from datetime import date
from unittest.mock import AsyncMock

import pytest

from src.exceptions.content import ArticleNotFoundError
from src.repositories.markdown_content import MarkdownContentRepository
from src.services.articles import ArticleService
from tests.helpers import make_article_item


def make_service(items: list) -> ArticleService:
    repository = AsyncMock(spec=MarkdownContentRepository)
    repository.get_all.return_value = items
    repository.get_by_slug.side_effect = lambda slug: next(
        (item for item in items if item.slug == slug), None
    )
    return ArticleService(articles_repository=repository)


ARTICLES = [
    make_article_item("older", title="Older post", published_at=date(2026, 1, 5)),
    make_article_item("newer", title="Newer AI post", category="ai", published_at=date(2026, 2, 1)),
    make_article_item("same-day-a", published_at=date(2026, 1, 20)),
    make_article_item("same-day-b", published_at=date(2026, 1, 20)),
    make_article_item("hidden-draft", title="Draft post", draft=True),
]


async def test_list_articles_excludes_drafts_and_sorts() -> None:
    service = make_service(ARTICLES)

    result = await service.list_articles(page=1, page_size=10, category=None, query=None)

    assert result.total == 4
    slugs = [item.slug for item in result.items]
    assert slugs == ["newer", "same-day-a", "same-day-b", "older"]
    assert "hidden-draft" not in slugs


async def test_list_articles_page_out_of_range_returns_empty_page() -> None:
    service = make_service(ARTICLES)

    result = await service.list_articles(page=99, page_size=10, category=None, query=None)

    assert result.items == []
    assert result.total == 4
    assert result.pages == 1


async def test_list_articles_paginates_with_boundaries() -> None:
    service = make_service(ARTICLES)

    first = await service.list_articles(page=1, page_size=3, category=None, query=None)
    second = await service.list_articles(page=2, page_size=3, category=None, query=None)

    assert len(first.items) == 3
    assert first.pages == 2
    assert [item.slug for item in second.items] == ["older"]


async def test_list_articles_filters_by_category_and_unknown_is_empty() -> None:
    service = make_service(ARTICLES)

    found = await service.list_articles(page=1, page_size=10, category="ai", query=None)
    missing = await service.list_articles(page=1, page_size=10, category="unknown", query=None)

    assert [item.slug for item in found.items] == ["newer"]
    assert missing.total == 0
    assert missing.items == []


async def test_list_articles_search_is_case_insensitive_and_covers_body() -> None:
    items = [
        make_article_item("body-match", title="Plain title", text="Deep dive into AsyncIO."),
    ]
    service = make_service(items)

    by_title = await service.list_articles(page=1, page_size=10, category=None, query="PLAIN")
    by_body = await service.list_articles(page=1, page_size=10, category=None, query="asyncio")

    assert by_title.total == 1
    assert by_body.total == 1


async def test_list_articles_search_does_not_match_drafts() -> None:
    items = [make_article_item("hidden-draft", title="Keyword here", draft=True)]
    service = make_service(items)

    result = await service.list_articles(page=1, page_size=10, category=None, query="keyword")

    assert result.total == 0


async def test_get_latest_respects_limit() -> None:
    service = make_service(ARTICLES)

    result = await service.get_latest(limit=2)

    assert [item.slug for item in result] == ["newer", "same-day-a"]


async def test_get_article_returns_detail_with_seo_defaults() -> None:
    service = make_service(ARTICLES)

    result = await service.get_article(slug="newer")

    assert result.payload.slug == "newer"
    assert result.payload.content_html
    assert result.payload.seo.title == "Newer AI post"
    assert result.payload.seo.og_image == "/og/bks-lab-default.jpg"
    assert result.content_hash


async def test_get_article_raises_not_found_for_missing_and_draft() -> None:
    service = make_service(ARTICLES)

    with pytest.raises(ArticleNotFoundError) as missing:
        await service.get_article(slug="nope")
    with pytest.raises(ArticleNotFoundError) as draft:
        await service.get_article(slug="hidden-draft")

    assert missing.value.status_code == 404
    assert draft.value.status_code == 404
