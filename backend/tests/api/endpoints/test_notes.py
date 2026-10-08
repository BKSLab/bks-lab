"""API contract tests for /api/v1/notes."""

from httpx import AsyncClient


async def test_list_notes_returns_paged_contract(client: AsyncClient) -> None:
    response = await client.get("/api/v1/notes")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3  # draft excluded; broken related link stays
    assert body["page_size"] == 20  # notes default differs from articles
    first = body["items"][0]
    assert first["slug"] == "note-two"  # newest first
    assert set(first) == {
        "slug", "title", "excerpt", "published_at", "reading_time",
        "tags", "related_article", "content_html",
    }
    assert first["excerpt"] == "Short note text."


async def test_list_notes_related_article_resolution(client: AsyncClient) -> None:
    response = await client.get("/api/v1/notes")

    by_slug = {item["slug"]: item for item in response.json()["items"]}
    assert by_slug["note-two"]["related_article"] == {
        "slug": "article-two",
        "title": "Second article about AI",
    }
    assert by_slug["note-broken-link"]["related_article"] is None
    assert by_slug["note-one"]["related_article"] is None


async def test_list_notes_pagination(client: AsyncClient) -> None:
    response = await client.get("/api/v1/notes", params={"page": 2, "page_size": 2})

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["pages"] == 2

    empty = await client.get("/api/v1/notes", params={"page": 99})
    assert empty.status_code == 200
    assert empty.json()["items"] == []


async def test_latest_notes(client: AsyncClient) -> None:
    response = await client.get("/api/v1/notes/latest", params={"limit": 2})

    assert response.status_code == 200
    body = response.json()
    assert [item["slug"] for item in body] == ["note-two", "note-broken-link"]
    assert (await client.get("/api/v1/notes/latest", params={"limit": 0})).status_code == 422
