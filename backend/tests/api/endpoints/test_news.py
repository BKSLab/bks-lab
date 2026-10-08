"""Protected News API behavior with real sessions and PostgreSQL storage."""

import ast
from pathlib import Path

import pytest
from fastapi.routing import APIRoute
from sqlalchemy import func, select

from main import app
from src.db.models import NewsJob, NewsSource
from src.dependencies.admin import check_admin_origin, require_admin
from src.repositories.news_items import NewsItemRepository
from src.repositories.news_jobs import NewsJobRepository
from tests.api.endpoints.test_admin import ORIGIN, admin_config as admin_config, login
from tests.news_helpers import add_source, collected

ROUTES = [
    ("GET", "/sources"),
    ("POST", "/sources"),
    ("POST", "/sources/discover"),
    ("PATCH", "/sources/1"),
    ("GET", "/topics"),
    ("POST", "/topics"),
    ("PATCH", "/topics/1"),
    ("GET", "/categories"),
    ("POST", "/categories"),
    ("PATCH", "/categories/1"),
    ("GET", "/items"),
    ("GET", "/items/1"),
    ("POST", "/items/1/decision"),
    ("POST", "/items/1/reanalyze"),
    ("POST", "/jobs/collect"),
    ("GET", "/jobs/1"),
    ("GET", "/runs"),
    ("GET", "/settings"),
    ("PATCH", "/settings"),
]


def test_news_routes_use_authentication_and_origin_dependencies_and_keep_layers():
    def calls(dependant):
        return {dependant.call}.union(
            *(calls(child) for child in dependant.dependencies)
        )

    routes = [
        route
        for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith("/api/admin/news/")
    ]
    assert len(routes) == len(ROUTES)
    for route in routes:
        assert {require_admin, check_admin_origin} <= calls(route.dependant)
    backend = Path(__file__).resolve().parents[3]
    for relative, forbidden in (
        ("src/api/news.py", ("sqlalchemy", "src.repositories", "src.db")),
        ("src/services/news_admin.py", ("sqlalchemy", "fastapi")),
    ):
        tree = ast.parse((backend / relative).read_text(encoding="utf-8"))
        imports = [
            node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
        ]
        assert not any(module and module.startswith(forbidden) for module in imports)


@pytest.mark.parametrize("method,path", ROUTES)
async def test_every_news_route_rejects_anonymous_with_no_store(client, method, path):
    response = await client.request(
        method,
        f"/api/admin/news{path}",
        headers=ORIGIN,
        json={} if method != "GET" else None,
    )
    assert response.status_code == 401
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    "method,path", [(method, path) for method, path in ROUTES if method != "GET"]
)
async def test_every_news_mutation_requires_trusted_origin(client, method, path):
    await login(client)
    response = await client.request(method, f"/api/admin/news{path}", json={})
    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"


async def complete_discovery(
    db_session, job_id, url="https://example.org/feed.xml", kind="rss"
):
    jobs = NewsJobRepository(db_session)
    claimed = await jobs.claim("preview-owner", 120, 3, kinds=["discover"])
    assert claimed.id == job_id
    assert await jobs.complete(
        job_id,
        "preview-owner",
        result={"kind": kind, "url": url, "items": [], "warnings": []},
    )


async def test_discovery_is_queued_and_source_requires_matching_completed_preview(
    client, db_session
):
    await login(client)
    response = await client.post(
        "/api/admin/news/sources/discover",
        json={"url": "https://example.org/", "config": {}},
        headers=ORIGIN,
    )
    assert response.status_code == 202 and response.json()["status"] == "queued"
    job_id = response.json()["job_id"]
    data = {
        "name": "Example",
        "url": "https://example.org/feed.xml",
        "kind": "rss",
        "config": {},
        "discovery_job_id": job_id,
    }
    assert (
        await client.post("/api/admin/news/sources", json=data, headers=ORIGIN)
    ).status_code == 409
    await complete_discovery(db_session, job_id)
    response = await client.post("/api/admin/news/sources", json=data, headers=ORIGIN)
    assert response.status_code == 201, response.text
    source_id = response.json()["id"]
    response = await client.patch(
        f"/api/admin/news/sources/{source_id}", json={"active": False}, headers=ORIGIN
    )
    assert response.status_code == 200 and response.json()["active"] is False
    assert (
        await client.patch(
            f"/api/admin/news/sources/{source_id}",
            json={"url": "https://example.org/other"},
            headers=ORIGIN,
        )
    ).status_code == 409
    assert (
        await client.patch(
            f"/api/admin/news/sources/{source_id}",
            json={"config": {"item_selector": "article"}, "discovery_job_id": job_id},
            headers=ORIGIN,
        )
    ).status_code == 409
    assert await db_session.scalar(select(func.count()).select_from(NewsSource)) == 1


async def test_matching_preview_allows_changed_source_configuration(client, db_session):
    source = await add_source(db_session)
    source_id = source.id
    await login(client)
    config = {"item_selector": "article", "title_selector": "h2", "link_selector": "a"}
    response = await client.post(
        "/api/admin/news/sources/discover",
        json={"url": "https://example.org/posts", "kind": "html", "config": config},
        headers=ORIGIN,
    )
    job_id = response.json()["job_id"]
    await complete_discovery(db_session, job_id, "https://example.org/posts", "html")
    response = await client.patch(
        f"/api/admin/news/sources/{source_id}",
        json={
            "url": "https://example.org/posts",
            "kind": "html",
            "config": config,
            "discovery_job_id": job_id,
        },
        headers=ORIGIN,
    )
    assert response.status_code == 200, response.text
    assert response.json()["kind"] == "html" and response.json()["config"] == config


async def test_catalog_validation_and_conflicts_map_to_safe_statuses(client):
    await login(client)
    created = await client.post(
        "/api/admin/news/topics", json={"name": "AI"}, headers=ORIGIN
    )
    assert created.status_code == 201
    duplicate = await client.post(
        "/api/admin/news/topics", json={"name": "AI"}, headers=ORIGIN
    )
    assert duplicate.status_code == 409
    assert "INSERT" not in duplicate.text and "news_topics" not in duplicate.text
    missing = await client.patch(
        "/api/admin/news/topics/999", json={"active": False}, headers=ORIGIN
    )
    assert missing.status_code == 404
    invalid = await client.patch(
        f"/api/admin/news/topics/{created.json()['id']}",
        json={"name": None},
        headers=ORIGIN,
    )
    assert invalid.status_code == 422


async def test_settings_validate_timezone_schedule_weights_and_hide_credentials(client):
    await login(client)
    response = await client.get("/api/admin/news/settings")
    assert response.status_code == 200
    assert {"llm_configured", "llm_provider", "llm_model"} <= response.json().keys()
    assert (
        not {"llm_api_key", "llm_api_url", "llm_monthly_budget", "llm_daily_limit"}
        & response.json().keys()
    )
    for patch in (
        {"timezone": "Wrong/Zone"},
        {"schedule": ["08:00", "08:00", "20:00"]},
        {
            "news_weights": {
                "topical_fit": 10,
                "significance": 10,
                "freshness": 10,
                "article_potential": 10,
            }
        },
        {"llm_api_key": "not-accepted"},
        {"enabled": None},
    ):
        assert (
            await client.patch("/api/admin/news/settings", json=patch, headers=ORIGIN)
        ).status_code == 422
    response = await client.patch(
        "/api/admin/news/settings",
        json={"enabled": False, "schedule": ["20:00", "08:00", "14:00"]},
        headers=ORIGIN,
    )
    assert response.status_code == 200
    assert response.json()["enabled"] is False and response.json()["schedule"] == [
        "08:00",
        "14:00",
        "20:00",
    ]


async def test_item_decisions_use_session_editor_and_remain_in_history(
    client, db_session
):
    source = await add_source(db_session)
    item_id = (
        await NewsItemRepository(db_session).ingest(source.id, [collected()], {})
    )["item_ids"][0]
    await login(client)
    data = {
        "decision": "in_work",
        "format": "longread_candidate",
        "comment": "Разобрать",
    }
    rejected = await client.post(
        f"/api/admin/news/items/{item_id}/decision",
        json={**data, "editor": "forged"},
        headers=ORIGIN,
    )
    assert rejected.status_code == 422
    for decision in ("in_work", "deferred"):
        response = await client.post(
            f"/api/admin/news/items/{item_id}/decision",
            json={**data, "decision": decision},
            headers=ORIGIN,
        )
        assert response.status_code == 200 and response.json()["editor"] == "test-admin"
    detail = await client.get(f"/api/admin/news/items/{item_id}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["decision"]["decision"] == "deferred"
    assert len(detail.json()["decision_history"]) == 2
    page = await client.get(
        "/api/admin/news/items", params={"status": "pending_analysis"}
    )
    assert page.status_code == 200 and page.json()["total"] == 1
    assert (
        await client.get("/api/admin/news/items", params={"page_size": 51})
    ).status_code == 422
    assert (
        await client.get(
            "/api/admin/news/items", params={"date_from": "2026-10-08T00:00:00"}
        )
    ).status_code == 422
    assert (
        await client.get(
            "/api/admin/news/items",
            params={
                "date_from": "2026-10-09T00:00:00Z",
                "date_to": "2026-10-08T00:00:00Z",
            },
        )
    ).status_code == 422


async def test_collect_and_reanalyze_return_durable_jobs_without_exposing_payload(
    client, db_session
):
    source = await add_source(db_session)
    source_id = source.id
    item_id = (
        await NewsItemRepository(db_session).ingest(source_id, [collected()], {})
    )["item_ids"][0]
    await login(client)
    collect = await client.post(
        "/api/admin/news/jobs/collect", json={"source_id": source_id}, headers=ORIGIN
    )
    reanalyze = await client.post(
        f"/api/admin/news/items/{item_id}/reanalyze", headers=ORIGIN
    )
    assert collect.status_code == reanalyze.status_code == 202
    assert await db_session.scalar(select(func.count()).select_from(NewsJob)) == 2
    response = await client.get(f"/api/admin/news/jobs/{reanalyze.json()['job_id']}")
    assert response.status_code == 200 and response.json()["kind"] == "analyze"
    assert not {"owner_token", "payload", "dedupe_key"} & response.json().keys()
