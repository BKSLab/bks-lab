"""Protected News API behavior with real sessions and PostgreSQL storage."""

import ast
from pathlib import Path

import pytest
from fastapi.routing import APIRoute
from sqlalchemy import func, select

from main import app
from src.db.models import NewsJob, NewsRunItem, NewsSource
from src.dependencies.admin import check_admin_origin, require_admin
from src.repositories.news_analyses import NewsAnalysisRepository
from src.repositories.news_items import NewsItemRepository
from src.repositories.news_jobs import NewsJobRepository
from src.repositories.news_runs import NewsRunRepository
from src.repositories.news_sources import NewsSourceRepository
from tests.api.endpoints.test_admin import ORIGIN, admin_config as admin_config, login
from tests.news_helpers import add_source, analysis_data, collected

ROUTES = [
    ("GET", "/sources"),
    ("GET", "/sources/example"),
    ("PATCH", "/sources/example"),
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
    ("GET", "/collection-status"),
    ("GET", "/jobs/example-2026-10-15-140000"),
    ("GET", "/jobs/example-2026-10-15-140000/runs"),
    ("GET", "/jobs/example-2026-10-15-140000/items"),
    ("GET", "/runs"),
    ("GET", "/settings"),
    ("PATCH", "/settings"),
    ("GET", "/note-settings"),
    ("PATCH", "/note-settings"),
    ("GET", "/note-queue"),
    ("PATCH", "/note-queue/example-note"),
]


async def test_sources_show_only_verified_profiles_and_no_adapter_controls(client, db_session):
    source = await add_source(db_session)
    legacy = await NewsSourceRepository(db_session).create({
        "name": "Historical source", "url": "https://old.example/feed", "kind": "rss",
        "config": {}, "active": True,
    })
    await login(client)
    response = await client.get("/api/admin/news/sources")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    entries = response.json()
    assert [entry["slug"] for entry in entries] == [source.slug]
    assert {"description", "active", "schedule", "next_check_at", "last_success_at", "health"} <= entries[0].keys()
    assert not {"kind", "config", "priority", "trust_score", "topic_ids", "category_ids", "profile_id"} & entries[0].keys()
    assert (await client.get(f"/api/admin/news/sources/{legacy.slug}")).status_code == 404
    assert await db_session.get(NewsSource, legacy.id) is not None


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


async def test_source_connection_endpoints_are_removed(client):
    await login(client)
    assert (await client.post("/api/admin/news/sources", json={}, headers=ORIGIN)).status_code == 405
    assert (await client.post("/api/admin/news/sources/discover", json={}, headers=ORIGIN)).status_code == 405
    assert (await client.get("/api/admin/news/sources/catalogue")).status_code == 404


async def test_source_preferences_accept_only_enablement_and_valid_calendar(client, db_session):
    source = await add_source(db_session)
    await login(client)
    schedule = {"mode": "weekly", "times": ["20:00", "08:00"], "weekdays": [5, 0]}
    response = await client.patch(
        f"/api/admin/news/sources/{source.slug}", json={"active": False, "schedule": schedule}, headers=ORIGIN,
    )
    assert response.status_code == 200, response.text
    assert response.json()["active"] is False
    assert response.json()["next_check_at"] is None
    assert response.json()["schedule"] == {"mode": "weekly", "times": ["08:00", "20:00"], "weekdays": [0, 5]}
    enabled = await client.patch(f"/api/admin/news/sources/{source.slug}", json={"active": True}, headers=ORIGIN)
    assert enabled.status_code == 200
    assert enabled.json()["next_check_at"] is not None
    for patch in (
        {"name": "Replacement"}, {"url": "https://other.example/feed"}, {"kind": "html"},
        {"config": {}}, {"priority": 90}, {"trust_score": 90}, {"topic_ids": []},
        {"interval_hours": 6}, {"active": None}, {"schedule": None},
        {"schedule": {"mode": "daily", "times": []}},
        {"schedule": {"mode": "daily", "times": ["08:00", "08:00"]}},
        {"schedule": {"mode": "daily", "times": ["8:00"]}},
        {"schedule": {"mode": "daily", "times": ["08:00"], "timezone": "UTC"}},
        {"schedule": {"mode": "weekly", "times": ["08:00"], "weekdays": []}},
        {"schedule": {"mode": "weekly", "times": ["08:00"], "weekdays": [0, 0]}},
        {"schedule": {"mode": "weekly", "times": ["08:00"], "weekdays": [7]}},
        {"schedule": {"mode": "interval_days", "times": ["08:00"], "every_days": 0, "start_date": "2026-10-15"}},
        {"schedule": {"mode": "interval_days", "times": ["08:00"], "every_days": 366, "start_date": "2026-10-15"}},
    ):
        invalid = await client.patch(f"/api/admin/news/sources/{source.slug}", json=patch, headers=ORIGIN)
        assert invalid.status_code == 422, (patch, invalid.text)


async def test_manual_collection_can_check_an_inactive_verified_source(client, db_session):
    source = await add_source(db_session)
    await NewsSourceRepository(db_session).update_preferences(source.id, {"active": False})
    await login(client)
    response = await client.post("/api/admin/news/jobs/collect", json={"source_slug": source.slug}, headers=ORIGIN)
    assert response.status_code == 202
    job = await NewsJobRepository(db_session).get(response.json()["job_id"])
    assert job.source_id == source.id
    assert "scheduled_slot" not in job.payload


async def test_collection_status_restores_safe_scope_and_rejects_noncollection_slugs(client, db_session):
    source = await add_source(db_session)
    await login(client)
    empty = await client.get("/api/admin/news/collection-status")
    assert empty.status_code == 200 and empty.headers["cache-control"] == "no-store"
    assert empty.json()["job"] is None and empty.json()["sources"] == []
    queued = await client.post("/api/admin/news/jobs/collect", json={}, headers=ORIGIN)
    slug = queued.json()["job_slug"]
    restored = await client.get("/api/admin/news/collection-status", params={"job_slug": slug})
    assert restored.status_code == 200 and restored.headers["cache-control"] == "no-store"
    body = restored.json()
    assert body["job"]["slug"] == slug and body["busy"] is True
    assert body["collection"]["sources_total"] == body["collection"]["sources_queued"] == 1
    assert body["sources"][0]["source_slug"] == source.slug
    assert body["analysis"]["scope"] == body["sources"][0]["analysis"]["scope"] == "new_updated"
    assert not {"id", "source_id", "item_id", "owner_token", "payload", "result"} & body["job"].keys()
    assert not {"id", "source_id", "item_id"} & body["sources"][0].keys()
    jobs = NewsJobRepository(db_session)
    discovery = await jobs.enqueue("discover", payload={"url": "https://example.org/feed"})
    for address in ("missing-collection", discovery.slug):
        response = await client.get("/api/admin/news/collection-status", params={"job_slug": address})
        assert response.status_code == 404 and response.headers["cache-control"] == "no-store"
    assert (await client.get("/api/admin/news/collection-status?job_slug=123")).status_code == 422


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


async def test_settings_validate_policy_weights_and_hide_credentials(client):
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
        json={"enabled": False},
        headers=ORIGIN,
    )
    assert response.status_code == 200
    assert response.json()["enabled"] is False
    assert not {"timezone", "schedule"} & response.json().keys()



async def test_publication_plan_preserves_material_data_without_duplicate_membership(
    client, db_session
):
    source = await add_source(db_session)
    items = NewsItemRepository(db_session)
    material = collected()
    item_id = (await items.ingest(source.id, [material], {}))["item_ids"][0]
    analysis = analysis_data()
    await NewsAnalysisRepository(db_session).save(
        item_id, material["content_hash"], "model", "v1", analysis
    )
    await items.ingest(
        source.id, [collected(external_id="two", url="https://example.org/two")], {}
    )
    await login(client)
    decision = {
        "decision": "in_work",
        "format": "short_news_candidate",
        "comment": "Check the figures before writing",
    }
    for _ in range(2):
        response = await client.post(
            f"/api/admin/news/items/{item_id}/decision",
            json=decision,
            headers=ORIGIN,
        )
        assert response.status_code == 200

    await items.ingest(source.id, [material], {})
    page = await client.get("/api/admin/news/items", params={"decision": "in_work"})
    assert page.status_code == 200
    assert page.json()["total"] == 1
    planned = page.json()["items"][0]
    assert planned["id"] == item_id
    assert planned["title"] == material["title"]
    assert planned["url"] == material["url"]
    assert planned["source_name"] == source.name
    assert planned["analysis"]["summary_ru"] == analysis["summary_ru"]
    assert planned["decision"]["format"] == decision["format"]
    assert planned["decision"]["comment"] == decision["comment"]

    removed = await client.post(
        f"/api/admin/news/items/{item_id}/decision",
        json={**decision, "decision": "deferred"},
        headers=ORIGIN,
    )
    assert removed.status_code == 200
    page = await client.get("/api/admin/news/items", params={"decision": "in_work"})
    assert page.json()["total"] == 0
    detail = await client.get(f"/api/admin/news/items/{item_id}")
    assert detail.status_code == 200
    assert detail.json()["content"] == material["content"]
    assert len(detail.json()["decision_history"]) == 3


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
        "/api/admin/news/jobs/collect", json={"source_slug": source.slug}, headers=ORIGIN
    )
    reanalyze = await client.post(
        f"/api/admin/news/items/{item_id}/reanalyze", headers=ORIGIN
    )
    assert collect.status_code == reanalyze.status_code == 202
    assert await db_session.scalar(select(func.count()).select_from(NewsJob)) == 2
    response = await client.get(f"/api/admin/news/jobs/{reanalyze.json()['job_slug']}")
    assert response.status_code == 200 and response.json()["kind"] == "analyze"
    assert not {"owner_token", "payload", "dedupe_key"} & response.json().keys()


async def test_analysis_states_distinguish_backlog_jobs_and_insufficient_text(client, db_session):
    source = await add_source(db_session)
    items = NewsItemRepository(db_session)
    item_id = (await items.ingest(source.id, [collected()], {}))["item_ids"][0]
    short_id = (await items.ingest(source.id, [collected(
        external_id="short", url="https://example.org/short", content="Model downloads: 12",
    )], {}))["item_ids"][0]
    await login(client)
    detail_url = f"/api/admin/news/items/{item_id}"
    assert (await client.get(detail_url)).json()["analysis_state"] == "pending"
    short = (await client.get(f"/api/admin/news/items/{short_id}")).json()
    assert short["analysis_state"] == "insufficient_text"
    rejected = await client.post(f"/api/admin/news/items/{short_id}/reanalyze", headers=ORIGIN)
    assert rejected.status_code == 422
    queued = await client.post(f"{detail_url}/reanalyze", headers=ORIGIN)
    assert queued.status_code == 202
    assert (await client.get(detail_url)).json()["analysis_state"] == "queued"
    jobs = NewsJobRepository(db_session)
    job = await jobs.claim(owner_token="test-worker", lease_seconds=60, max_attempts=1, kinds=["analyze"])
    assert (await client.get(detail_url)).json()["analysis_state"] == "running"
    await jobs.fail(job.id, "test-worker", error="Ответ модели не прошёл проверку.", retry=False, max_attempts=1)
    detail = (await client.get(detail_url)).json()
    assert detail["analysis_state"] == "failed" and detail["analysis_error"] == "Ответ модели не прошёл проверку."
    page = (await client.get("/api/admin/news/items")).json()
    assert {row["analysis_state"] for row in page["items"]} == {"failed", "insufficient_text"}


async def test_job_reports_use_slugs_snapshot_sources_and_filter_observations(client, db_session):
    source = await add_source(db_session, name="Исследования ИИ")
    source_id, source_slug = source.id, source.slug
    jobs, runs = NewsJobRepository(db_session), NewsRunRepository(db_session)
    collection = await jobs.enqueue("collect", source_id=source_id)
    run = await runs.begin(source_id, collection.id, parameters={"initial_lookback_days": 30})
    material = collected()
    item_id = (await NewsItemRepository(db_session).ingest(source_id, [material], {}))["item_ids"][0]
    db_session.add_all([
        NewsRunItem(run_id=run.id, item_id=item_id, title=material["title"], url=material["url"], content_hash=material["content_hash"], outcome="unchanged", warning="Article fetch failed.", preserved_previous=True),
        NewsRunItem(run_id=run.id, title="Old candidate", url="https://example.org/old", outcome="skipped", reason="Outside the collection window.", stage="listing"),
    ])
    await db_session.commit()
    analysis_job = await jobs.enqueue("analyze", item_id=item_id, payload={"content_hash": material["content_hash"]})
    await runs.finish(run.id, "completed", unchanged_count=1, skipped_count=1, warning_count=1, not_modified=False, http_status=200, diagnostics_truncated=True)
    await NewsSourceRepository(db_session).update(source_id, {"name": "Renamed source"})
    await login(client)
    root = f"/api/admin/news/jobs/{collection.slug}"
    response = await client.get(root)
    assert response.status_code == 200 and response.json()["source_slug"] == source_slug
    assert response.json()["source_name"] == "Renamed source"
    assert not {"owner_token", "payload", "dedupe_key"} & response.json().keys()
    response = await client.get(f"{root}/runs")
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    entry = response.json()["items"][0]
    assert entry["source_name"] == "Исследования ИИ"
    assert entry["source_slug"] == source_slug and entry["job_slug"] == collection.slug
    assert entry["http_status"] == 200 and entry["diagnostics_truncated"] is True
    assert entry["parameters"] == {"initial_lookback_days": 30}
    response = await client.get(f"{root}/items", params={"warnings_only": "true", "source_slug": source_slug})
    assert response.status_code == 200 and response.json()["total"] == 1
    observation = response.json()["items"][0]
    assert observation["outcome"] == "unchanged" and observation["preserved_previous"] is True
    assert observation["analysis_status"] == "queued" and observation["analysis_job_slug"] == analysis_job.slug
    claimed = await jobs.claim("skipped-analysis-worker", 120, 3, kinds=["analyze"])
    assert claimed.id == analysis_job.id
    await jobs.complete(analysis_job.id, "skipped-analysis-worker", result={"skipped": "content_changed"})
    response = await client.get(f"{root}/items", params={"warnings_only": "true"})
    observation = response.json()["items"][0]
    assert observation["analysis_status"] == "skipped"
    assert observation["analysis_reason"] == "Версия материала изменилась до завершения анализа."
    assert observation["analysis_job_slug"] == analysis_job.slug
    await NewsAnalysisRepository(db_session).save(item_id, material["content_hash"], "model", "v1", analysis_data())
    observation = (await client.get(f"{root}/items", params={"warnings_only": "true"})).json()["items"][0]
    assert observation["analysis_status"] == "completed" and observation["analysis_reason"] is None
    skipped = await client.get(f"{root}/items", params={"outcome": "skipped"})
    assert skipped.json()["total"] == 1 and skipped.json()["items"][0]["analysis_status"] is None
    assert (await client.get(f"{root}/items", params={"outcome": "other"})).status_code == 422
    assert (await client.get(f"{root}/items", params={"page_size": 51})).status_code == 422
    assert (await client.get("/api/admin/news/jobs/missing-job/items")).status_code == 404
    assert (await client.get(f"/api/admin/news/jobs/{collection.id}")).status_code == 422
    assert (await client.patch(f"/api/admin/news/sources/{source_id}", json={"active": False}, headers=ORIGIN)).status_code == 422
    assert (await client.post("/api/admin/news/jobs/collect", json={"source_id": source_id}, headers=ORIGIN)).status_code == 422
    assert (await client.get("/api/admin/news/items", params={"source_slug": source_slug})).json()["total"] == 1
    source_response = await client.get(f"/api/admin/news/sources/{source_slug}")
    assert source_response.status_code == 200 and source_response.json()["name"] == "Renamed source"
    assert source_response.json()["slug"] == source_slug
    assert source_response.headers["cache-control"] == "no-store"
    assert (await client.get("/api/admin/news/sources/missing-source")).status_code == 404
    assert (await client.get(f"/api/admin/news/sources/{source_id}")).status_code == 422
    for reserved_name in ("New", "Catalogue", "Discover"):
        reserved = await add_source(db_session, name=reserved_name)
        assert reserved.slug == f"source-{reserved_name.lower()}"
        assert (await client.get(f"/api/admin/news/sources/{reserved.slug}")).json()["name"] == reserved_name
