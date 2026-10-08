"""API contract tests for /api/v1/articles."""

from httpx import AsyncClient


async def test_list_articles_returns_paged_contract(client: AsyncClient) -> None:
    response = await client.get("/api/v1/articles")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"items", "total", "page", "page_size", "pages"}
    assert body["total"] == 2  # draft and invalid files are excluded
    assert body["page"] == 1
    assert body["page_size"] == 10
    assert body["pages"] == 1
    assert response.headers["Cache-Control"] == "public, max-age=60"
    first = body["items"][0]
    assert first["slug"] == "article-two"  # newest first
    assert set(first) == {
        "slug", "title", "excerpt", "category", "published_at",
        "reading_time", "cover_image", "tags",
    }
    assert first["reading_time"] >= 1


async def test_list_articles_page_out_of_range_returns_empty_200(client: AsyncClient) -> None:
    response = await client.get("/api/v1/articles", params={"page": 99})

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["total"] == 2


async def test_list_articles_pagination_boundaries(client: AsyncClient) -> None:
    response = await client.get("/api/v1/articles", params={"page": 2, "page_size": 1})

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["pages"] == 2

    assert (await client.get("/api/v1/articles", params={"page": 0})).status_code == 422
    assert (await client.get("/api/v1/articles", params={"page_size": 51})).status_code == 422


async def test_list_articles_category_filter(client: AsyncClient) -> None:
    found = await client.get("/api/v1/articles", params={"category": "development"})
    unknown = await client.get("/api/v1/articles", params={"category": "nope"})

    assert [item["slug"] for item in found.json()["items"]] == ["article-one"]
    assert unknown.status_code == 200
    assert unknown.json()["total"] == 0


async def test_list_articles_search_is_case_insensitive(client: AsyncClient) -> None:
    by_title = await client.get("/api/v1/articles", params={"q": "ai"})
    by_body = await client.get("/api/v1/articles", params={"q": "ASYNC patterns"})

    assert by_title.json()["total"] == 1
    assert by_title.json()["items"][0]["slug"] == "article-two"
    assert by_body.json()["total"] == 1


async def test_list_articles_search_min_length(client: AsyncClient) -> None:
    response = await client.get("/api/v1/articles", params={"q": "a"})

    assert response.status_code == 422


async def test_list_articles_search_excludes_drafts(client: AsyncClient) -> None:
    response = await client.get("/api/v1/articles", params={"q": "draft"})

    assert response.json()["total"] == 0


async def test_latest_articles(client: AsyncClient) -> None:
    response = await client.get("/api/v1/articles/latest", params={"limit": 1})

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) == 1
    assert body[0]["slug"] == "article-two"
    assert (await client.get("/api/v1/articles/latest", params={"limit": 11})).status_code == 422


async def test_get_article_returns_detail_with_etag(client: AsyncClient) -> None:
    response = await client.get("/api/v1/articles/article-two")

    assert response.status_code == 200
    body = response.json()
    assert body["slug"] == "article-two"
    assert "<p>" in body["content_html"]
    assert body["seo"]["title"] == "Second article about AI"
    assert body["seo"]["og_image"] == "/og/bks-lab-default.jpg"
    assert response.headers["ETag"].startswith('"')


async def test_get_article_404_for_missing_and_draft(client: AsyncClient) -> None:
    missing = await client.get("/api/v1/articles/no-such-article")
    draft = await client.get("/api/v1/articles/article-draft")

    assert missing.status_code == 404
    assert "detail" in missing.json()
    assert draft.status_code == 404
