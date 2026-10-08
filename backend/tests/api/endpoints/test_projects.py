"""API contract tests for /api/v1/projects and /api/v1/categories."""

from httpx import AsyncClient


async def test_list_projects_excludes_drafts_keeps_archived(client: AsyncClient) -> None:
    response = await client.get("/api/v1/projects")

    assert response.status_code == 200
    body = response.json()
    assert [item["slug"] for item in body] == ["project-one", "project-two", "project-archived"]
    assert body[2]["status"] == "archived"
    assert set(body[0]) == {
        "slug", "title", "excerpt", "cover_image", "tags", "status", "featured", "order",
    }
    assert response.headers["Cache-Control"] == "public, max-age=60"


async def test_list_projects_featured_filter(client: AsyncClient) -> None:
    featured = await client.get("/api/v1/projects", params={"featured": True})
    not_featured = await client.get("/api/v1/projects", params={"featured": False})

    assert [item["slug"] for item in featured.json()] == ["project-one"]
    assert [item["slug"] for item in not_featured.json()] == ["project-two", "project-archived"]


async def test_get_project_detail(client: AsyncClient) -> None:
    response = await client.get("/api/v1/projects/project-archived")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "archived"
    assert "<p>" in body["content_html"]
    assert body["seo"]["og_image"] == "/og/bks-lab-default.jpg"
    assert response.headers["ETag"].startswith('"')


async def test_get_project_404_for_missing_and_draft(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/projects/nope")).status_code == 404
    assert (await client.get("/api/v1/projects/project-draft")).status_code == 404


async def test_list_categories_includes_zero_counts(client: AsyncClient) -> None:
    response = await client.get("/api/v1/categories")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 5
    by_slug = {item["slug"]: item for item in body}
    assert by_slug["development"]["title"] == "Разработка"
    assert by_slug["development"]["articles_count"] == 1
    assert by_slug["ai"]["articles_count"] == 1
    assert by_slug["thoughts"]["articles_count"] == 0
