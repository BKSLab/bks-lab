"""API contract tests for the admin content editor (CRUD, statuses, revisions)."""

import pytest
from pydantic import SecretStr

from src.core.settings import get_settings
from src.dependencies.services import get_revalidation_client

LOGIN = {"username": "test-admin", "password": "test-only-password"}
ORIGIN = {"Origin": "http://test"}

ARTICLE_PAYLOAD = {
    "type": "article",
    "slug": "brand-new-article",
    "title": "Brand new article",
    "excerpt": "Excerpt of the brand new article.",
    "category": "development",
    "published_at": "2026-02-21",
    "cover_image": "/images/articles/brand-new-article.webp",
    "tags": ["new"],
    "content_markdown": "Body of the brand new article.",
}


@pytest.fixture(autouse=True)
def admin_config(monkeypatch):
    settings = get_settings().admin
    monkeypatch.setattr(settings, "username", LOGIN["username"])
    monkeypatch.setattr(settings, "password", SecretStr(LOGIN["password"]))
    monkeypatch.setattr(settings, "allowed_origins", ("http://test",))
    monkeypatch.setattr(settings, "cookie_secure", False)


async def login(client) -> None:
    response = await client.post("/api/admin/auth/login", json=LOGIN, headers=ORIGIN)
    assert response.status_code == 200


@pytest.mark.parametrize("method,url", [
    ("post", "/api/admin/content"),
    ("patch", "/api/admin/content/1"),
    ("delete", "/api/admin/content/1"),
    ("post", "/api/admin/content/1/status"),
    ("get", "/api/admin/content/1/revisions"),
    ("get", "/api/admin/content/1/revisions/1"),
    ("post", "/api/admin/content/1/revisions/1/restore"),
    ("post", "/api/admin/content/preview"),
])
async def test_editor_endpoints_reject_anonymous_requests(client, method, url):
    response = await getattr(client, method)(url, headers=ORIGIN)

    assert response.status_code == 401
    assert response.headers["cache-control"] == "no-store"


async def test_mutations_reject_untrusted_origin(client):
    await login(client)

    response = await client.post(
        "/api/admin/content", json=ARTICLE_PAYLOAD, headers={"Origin": "https://evil.example"}
    )

    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"


async def test_preview_rejects_untrusted_origin(client):
    await login(client)

    response = await client.post(
        "/api/admin/content/preview",
        json={"content_markdown": "# Title"},
        headers={"Origin": "https://evil.example"},
    )

    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"


async def test_preview_renders_markdown_like_the_save_pipeline(client):
    await login(client)

    response = await client.post(
        "/api/admin/content/preview",
        json={"content_markdown": "# Heading\n\nText with a [link](https://bks-lab.ru) and `code`."},
        headers=ORIGIN,
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    html = response.json()["html"]
    assert "<h1>Heading</h1>" in html
    assert '<a href="https://bks-lab.ru">link</a>' in html
    assert "<code>code</code>" in html


async def test_preview_rejects_empty_or_too_long_input(client):
    await login(client)

    for content_markdown in ("", "x" * 100_001):
        response = await client.post(
            "/api/admin/content/preview",
            json={"content_markdown": content_markdown},
            headers=ORIGIN,
        )

        assert response.status_code == 422


async def test_create_article_draft_is_stored_with_revision_but_not_published(client, session_factory):
    await login(client)

    created = await client.post("/api/admin/content", json=ARTICLE_PAYLOAD, headers=ORIGIN)

    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "draft"
    assert body["slug"] == "brand-new-article"
    assert body["content_markdown"] == "Body of the brand new article."
    assert body["word_count"] == 6
    assert body["created_at"] and body["updated_at"]

    # Drafts never appear in the public API.
    assert (await client.get("/api/v1/articles/brand-new-article")).status_code == 404
    listed = await client.get("/api/v1/articles")
    assert "brand-new-article" not in {item["slug"] for item in listed.json()["items"]}

    detail = await client.get(f"/api/admin/content/{body['id']}")
    assert detail.json()["content_markdown"] == "Body of the brand new article."

    revisions = await client.get(f"/api/admin/content/{body['id']}/revisions")
    assert [row["revision_no"] for row in revisions.json()] == [1]
    assert revisions.json()[0]["word_count"] == 6


async def test_create_note_and_project_by_their_own_rules(client):
    await login(client)

    note = await client.post(
        "/api/admin/content",
        json={
            "type": "note", "slug": "brand-new-note", "title": "Brand new note",
            "published_at": "2026-02-21", "related_slug": "article-one",
            "content_markdown": "First paragraph of the note.\n\nSecond paragraph.",
        },
        headers=ORIGIN,
    )
    project = await client.post(
        "/api/admin/content",
        json={
            "type": "project", "slug": "brand-new-project", "title": "Brand new project",
            "excerpt": "Excerpt.", "cover_image": "/images/projects/brand-new-project.webp",
            "tags": ["FastAPI"], "status": "active", "featured": True, "sort_order": 5,
            "draft": False, "content_markdown": "Project body.",
        },
        headers=ORIGIN,
    )

    assert note.status_code == 201
    assert note.json()["status"] == "draft"
    assert project.status_code == 201
    assert project.json()["status"] == "active"  # draft=false keeps the lifecycle status
    assert project.json()["featured"] is True


@pytest.mark.parametrize("payload", [
    {**ARTICLE_PAYLOAD, "slug": "Bad_Slug"},
    {key: value for key, value in ARTICLE_PAYLOAD.items() if key != "category"},
    {**ARTICLE_PAYLOAD, "type": "unknown"},
])
async def test_create_validation_errors(client, payload):
    await login(client)

    response = await client.post("/api/admin/content", json=payload, headers=ORIGIN)

    assert response.status_code == 422


async def test_create_conflicting_slug_returns_409(client):
    await login(client)

    response = await client.post(
        "/api/admin/content", json={**ARTICLE_PAYLOAD, "slug": "article-one"}, headers=ORIGIN
    )

    assert response.status_code == 409
    assert response.headers["cache-control"] == "no-store"


async def test_patch_updates_and_records_revision(client):
    await login(client)
    detail = (await client.get("/api/admin/content?type=article&q=First")).json()["items"][0]

    updated = await client.patch(
        f"/api/admin/content/{detail['id']}", json={"title": "Renamed article"}, headers=ORIGIN
    )

    assert updated.status_code == 200
    assert updated.json()["title"] == "Renamed article"
    revisions = (await client.get(f"/api/admin/content/{detail['id']}/revisions")).json()
    assert [row["revision_no"] for row in revisions] == [2, 1]
    snapshot = (await client.get(f"/api/admin/content/{detail['id']}/revisions/2")).json()
    assert snapshot["snapshot"]["title"] == "Renamed article"
    public = await client.get("/api/v1/articles/article-one")
    assert public.json()["title"] == "Renamed article"


async def test_patch_with_state_invalid_for_the_type_returns_422(client):
    await login(client)
    project = (await client.get("/api/admin/content?type=project")).json()["items"][0]

    response = await client.patch(
        f"/api/admin/content/{project['id']}", json={"tags": []}, headers=ORIGIN
    )

    assert response.status_code == 422


async def test_status_transitions_and_visibility(client):
    await login(client)
    note = (await client.get("/api/admin/content?type=note&q=First")).json()["items"][0]
    project = (await client.get("/api/admin/content?type=project&q=Second")).json()["items"][0]
    article = (await client.get("/api/admin/content?type=article&q=First")).json()["items"][0]

    archived_note = await client.post(
        f"/api/admin/content/{note['id']}/status", json={"status": "archived"}, headers=ORIGIN
    )
    assert archived_note.status_code == 422  # archived is projects-only

    archived_project = await client.post(
        f"/api/admin/content/{project['id']}/status", json={"status": "archived"}, headers=ORIGIN
    )
    assert archived_project.status_code == 200
    assert archived_project.json()["status"] == "archived"
    public_projects = {item["slug"]: item for item in (await client.get("/api/v1/projects")).json()}
    assert public_projects["project-two"]["status"] == "archived"

    drafted = await client.post(
        f"/api/admin/content/{article['id']}/status", json={"status": "draft"}, headers=ORIGIN
    )
    assert drafted.status_code == 200
    assert (await client.get("/api/v1/articles/article-one")).status_code == 404
    revisions = (await client.get(f"/api/admin/content/{article['id']}/revisions")).json()
    assert revisions[0]["revision_no"] == 2  # status change records a revision

    back = await client.post(
        f"/api/admin/content/{article['id']}/status", json={"status": "active"}, headers=ORIGIN
    )
    assert back.status_code == 200
    assert (await client.get("/api/v1/articles/article-one")).status_code == 200


async def test_restore_rewrites_material_and_appends_revision(client):
    await login(client)
    created = (await client.post("/api/admin/content", json=ARTICLE_PAYLOAD, headers=ORIGIN)).json()
    await client.patch(
        f"/api/admin/content/{created['id']}", json={"title": "Broken title"}, headers=ORIGIN
    )

    restored = await client.post(
        f"/api/admin/content/{created['id']}/revisions/1/restore", headers=ORIGIN
    )

    assert restored.status_code == 200
    assert restored.json()["title"] == "Brand new article"
    revisions = (await client.get(f"/api/admin/content/{created['id']}/revisions")).json()
    assert [row["revision_no"] for row in revisions] == [3, 2, 1]
    latest = (await client.get(f"/api/admin/content/{created['id']}/revisions/3")).json()
    first = (await client.get(f"/api/admin/content/{created['id']}/revisions/1")).json()
    assert latest["snapshot"] == first["snapshot"]
    missing = await client.post(
        f"/api/admin/content/{created['id']}/revisions/99/restore", headers=ORIGIN
    )
    assert missing.status_code == 404


async def test_delete_removes_material_and_its_history(client):
    await login(client)
    created = (await client.post("/api/admin/content", json=ARTICLE_PAYLOAD, headers=ORIGIN)).json()

    deleted = await client.delete(f"/api/admin/content/{created['id']}", headers=ORIGIN)

    assert deleted.status_code == 204
    assert (await client.get(f"/api/admin/content/{created['id']}")).status_code == 404
    assert (await client.get(f"/api/admin/content/{created['id']}/revisions")).status_code == 404
    again = await client.delete(f"/api/admin/content/{created['id']}", headers=ORIGIN)
    assert again.status_code == 404


async def test_mutation_calls_the_revalidation_webhook(client):
    from unittest.mock import AsyncMock

    from main import app
    from src.clients.revalidation import RevalidationClient

    revalidator = AsyncMock(spec=RevalidationClient)
    app.dependency_overrides[get_revalidation_client] = lambda: revalidator
    await login(client)

    await client.post("/api/admin/content", json=ARTICLE_PAYLOAD, headers=ORIGIN)

    revalidator.revalidate_content.assert_called_once()


async def test_ad_marker_is_stored_as_placeholder_in_content_html(client):
    await login(client)
    payload = {
        **ARTICLE_PAYLOAD,
        "slug": "article-with-ad",
        "content_markdown": "Первый абзац.\n\n::ad\n\nВторой абзац.",
    }

    created = await client.post("/api/admin/content", json=payload, headers=ORIGIN)

    assert created.status_code == 201
    public = await client.get("/api/v1/articles/article-with-ad")
    # The material is a draft: publish it first, then read the public HTML.
    assert public.status_code == 404
    await client.post(
        f"/api/admin/content/{created.json()['id']}/status",
        json={"status": "active"}, headers=ORIGIN,
    )
    public = await client.get("/api/v1/articles/article-with-ad")
    assert '<div data-ad-slot="article-inline"></div>' in public.json()["content_html"]


@pytest.mark.parametrize("content_markdown", [
    "::ad\n\nПервый абзац.\n\nВторой абзац.",  # marker first
    "Первый абзац.\n\nВторой абзац.\n\n::ad",  # marker last
    "А.\n\n::ad\n\nБ.\n\n::ad\n\nВ.\n\n::ad\n\nГ.",  # three markers
])
async def test_create_article_rejects_misplaced_ad_markers(client, content_markdown):
    await login(client)

    response = await client.post(
        "/api/admin/content",
        json={**ARTICLE_PAYLOAD, "content_markdown": content_markdown},
        headers=ORIGIN,
    )

    assert response.status_code == 422


async def test_ad_markers_are_rejected_in_notes(client):
    await login(client)

    response = await client.post(
        "/api/admin/content",
        json={
            "type": "note", "slug": "note-with-ad", "title": "Note with ad",
            "published_at": "2026-02-21",
            "content_markdown": "Первый абзац.\n\n::ad\n\nВторой абзац.",
        },
        headers=ORIGIN,
    )

    assert response.status_code == 422
