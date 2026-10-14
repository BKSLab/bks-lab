"""PostgreSQL regressions for collection quality and bounded archive repairs."""

import asyncio

import pytest
from sqlalchemy import func, select

from src.clients.news_sources import normalize_url, prepare_collected_item
from src.db.models import NewsAnalysis, NewsItem, NewsJob
from src.exceptions.news import NewsConflictError
from src.repositories.news_analyses import NewsAnalysisRepository
from src.repositories.news_decisions import NewsDecisionRepository
from src.repositories.news_items import NewsItemRepository
from src.repositories.news_jobs import NewsJobRepository
from src.repositories.news_sources import NewsSourceRepository
from src.schemas.news_collection import NEWS_MIN_CONTENT_CHARS, CollectedItem
from tests.news_helpers import add_source, analysis_data, collected


@pytest.mark.parametrize("status,text", [
    ("fetch_failed", ""),
    ("insufficient_text", "Only a navigation card"),
    ("fetch_failed", "A fallback source description with limited context. " * 6),
])
async def test_degraded_collection_preserves_text_hash_analysis_and_warning(db_session, status, text):
    source = await add_source(db_session)
    items = NewsItemRepository(db_session)
    original = collected()
    original["metadata_json"] = {"language": "en", "collection_status": "ready"}
    item_id = (await items.ingest(source.id, [original], {}))["item_ids"][0]
    analysis = await NewsAnalysisRepository(db_session).save(
        item_id, original["content_hash"], "model", "v1", analysis_data(),
    )
    degraded = collected(title="Incomplete source title", content=text)
    degraded["metadata_json"] = {"collection_status": status, "collection_warning": "Source text unavailable"}

    for _ in range(2):
        result = await items.ingest(source.id, [degraded], {}, collection_warning="Source text unavailable")
        assert result == {"new": 0, "updated": 0, "unchanged": 1, "item_ids": [item_id]}

    current = await items.get(item_id)
    for field in ("title", "content", "excerpt", "content_hash"):
        assert getattr(current, field) == original[field]
    assert current.status == "analyzed"
    assert current.latest_analysis_id == analysis.id
    assert current.metadata_json["collection_status"] == "ready"
    assert current.metadata_json["collection_warning"]
    assert current.metadata_json["language"] == "en"
    assert await db_session.scalar(select(func.count()).select_from(NewsItem)) == 1
    assert await db_session.scalar(select(func.count()).select_from(NewsAnalysis)) == 1
    assert await items.pending(20, "model", "v1") == []
    refreshed_source = await NewsSourceRepository(db_session).get(source.id)
    assert refreshed_source.health == "degraded"
    assert refreshed_source.last_error == "Source text unavailable"


async def test_identical_successful_collection_preserves_one_item_and_analysis(db_session):
    source = await add_source(db_session)
    items = NewsItemRepository(db_session)
    analyses = NewsAnalysisRepository(db_session)
    data = collected()
    item_id = (await items.ingest(source.id, [data], {}))["item_ids"][0]
    original = await analyses.save(item_id, data["content_hash"], "model", "v1", analysis_data())

    result = await items.ingest(source.id, [data], {"pass": 2})
    repeated = await analyses.save(item_id, data["content_hash"], "model", "v1", analysis_data())

    assert result == {"new": 0, "updated": 0, "unchanged": 1, "item_ids": [item_id]}
    assert repeated.id == original.id
    assert (await items.get(item_id)).latest_analysis_id == original.id
    assert await db_session.scalar(select(func.count()).select_from(NewsItem)) == 1
    assert await db_session.scalar(select(func.count()).select_from(NewsAnalysis)) == 1


async def test_pending_requires_minimum_text_in_content_or_excerpt(db_session):
    source = await add_source(db_session)
    items = NewsItemRepository(db_session)
    short = collected(external_id="short", url="https://example.org/short", content="a" * (NEWS_MIN_CONTENT_CHARS - 1))
    content = collected(external_id="content", url="https://example.org/content", content="b" * NEWS_MIN_CONTENT_CHARS)
    excerpt = collected(external_id="excerpt", url="https://example.org/excerpt", content="")
    excerpt["excerpt"] = "c" * NEWS_MIN_CONTENT_CHARS
    ids = (await items.ingest(source.id, [short, content, excerpt], {}))["item_ids"]

    assert {row.id for row in await items.pending(20, "model", "v1")} == set(ids[1:])
    assert {row.id for row in await items.pending(20)} == set(ids[1:])


async def test_pending_excludes_current_active_manual_repair_and_terminal_base_jobs(db_session):
    source = await add_source(db_session)
    items = NewsItemRepository(db_session)
    jobs = NewsJobRepository(db_session)
    data = [collected(external_id=str(index), url=f"https://example.org/{index}") for index in range(5)]
    failed_id, repair_id, manual_id, changed_id, fresh_id = (await items.ingest(source.id, data, {}))["item_ids"]
    content_hash = data[0]["content_hash"]

    base = await jobs.enqueue(
        "analyze", item_id=failed_id,
        dedupe_key=f"analysis:{failed_id}:{content_hash}:model:v1", payload={"content_hash": content_hash},
    )
    assert (await jobs.claim("failed-owner", 120, 1, kinds=["analyze"])).id == base.id
    assert await jobs.fail(base.id, "failed-owner", "Provider unavailable", retry=False, max_attempts=1)
    repair = await jobs.enqueue(
        "analyze", item_id=repair_id, dedupe_key=f"repair-analysis:{repair_id}:fixture",
        payload={"content_hash": content_hash, "force": True},
    )
    assert (await jobs.claim("repair-owner", 120, 3, kinds=["analyze"])).id == repair.id
    await jobs.enqueue("analyze", item_id=manual_id, payload={"content_hash": content_hash, "force": True})
    await jobs.enqueue("analyze", item_id=changed_id, payload={"content_hash": "obsolete-version", "force": True})

    assert {row.id for row in await items.pending(20, "model", "v1")} == {changed_id, fresh_id}


async def test_concurrent_repair_enqueue_reuses_batches_until_completion(session_factory):
    async with session_factory() as session:
        source = await add_source(session)
        data = [collected(external_id=str(index), url=f"https://example.org/{index}") for index in range(103)]
        item_ids = (await NewsItemRepository(session).ingest(source.id, data, {}))["item_ids"]
        source_id = source.id

    async def enqueue():
        async with session_factory() as session:
            return await NewsJobRepository(session).enqueue_repair(source_id, list(reversed(item_ids)) + item_ids[:3])

    results = await asyncio.gather(*(enqueue() for _ in range(3)))
    original_ids = [row.id for row in results[0]]
    assert all([row.id for row in rows] == original_ids for rows in results)
    assert [len(row.payload["repair_item_ids"]) for row in results[0]] == [50, 50, 3]
    assert [item_id for row in results[0] for item_id in row.payload["repair_item_ids"]] == sorted(item_ids)

    async with session_factory() as session:
        jobs = NewsJobRepository(session)
        first = await jobs.claim("repair-0", 120, 3, kinds=["collect"])
        assert first.id == original_ids[0]
        repeated = await jobs.enqueue_repair(source_id, item_ids)
        assert [row.id for row in repeated] == original_ids
        assert await session.scalar(select(func.count()).select_from(NewsJob)) == 3
        assert await jobs.complete(first.id, "repair-0")
        for index, job_id in enumerate(original_ids[1:], start=1):
            owner = f"repair-{index}"
            assert (await jobs.claim(owner, 120, 3, kinds=["collect"])).id == job_id
            assert await jobs.complete(job_id, owner)
        reapplied = await jobs.enqueue_repair(source_id, item_ids)
        assert len(reapplied) == 3
        assert not set(original_ids).intersection(row.id for row in reapplied)
        assert await session.scalar(select(func.count()).select_from(NewsJob)) == 6


async def test_repair_identity_survives_canonical_change_and_keeps_decisions(db_session):
    source = await add_source(db_session)
    items = NewsItemRepository(db_session)
    original = collected(external_id=None)
    item_id = (await items.ingest(source.id, [original], {}))["item_ids"][0]
    analysis = await NewsAnalysisRepository(db_session).save(
        item_id, original["content_hash"], "model", "v1", analysis_data(),
    )
    decisions = NewsDecisionRepository(db_session)
    decision = await decisions.create(item_id, {
        "decision": "in_work", "format": "longread_candidate", "editor": "admin", "comment": "Keep this decision",
    })
    repaired = collected(
        external_id=None, url="https://example.org/new-canonical", content="Repaired article with complete source text. " * 20,
    )
    repaired["existing_item_id"] = item_id
    repaired["metadata_json"] = {"collection_status": "ready"}

    result = await items.ingest(source.id, [repaired], {})

    assert result == {"new": 0, "updated": 1, "unchanged": 0, "item_ids": [item_id]}
    current = await items.get(item_id)
    assert current.normalized_url == repaired["normalized_url"]
    assert current.content == repaired["content"]
    assert current.status == "pending_analysis" and current.latest_analysis_id is None
    assert current.latest_decision_id == decision.id
    assert [row.id for row in await decisions.list_for_item(item_id)] == [decision.id]
    assert [row.id for row in await NewsAnalysisRepository(db_session).list_for_item(item_id)] == [analysis.id]
    assert await db_session.scalar(select(func.count()).select_from(NewsItem)) == 1


async def test_repair_does_not_create_missing_ids_or_touch_other_sources(db_session):
    source = await add_source(db_session)
    other_source = await add_source(db_session, name="Other", url="https://other.example.org/feed")
    items = NewsItemRepository(db_session)
    original = collected()
    item_id = (await items.ingest(other_source.id, [original], {}))["item_ids"][0]
    foreign = {**collected(content="Replacement article body. " * 20), "existing_item_id": item_id}
    missing = {**collected(external_id="missing", url="https://example.org/missing"), "existing_item_id": item_id + 1000}

    result = await items.ingest(source.id, [foreign, missing], {})

    assert result == {"new": 0, "updated": 0, "unchanged": 0, "item_ids": []}
    current = await items.get(item_id)
    assert current.source_id == other_source.id and current.content == original["content"]
    assert await db_session.scalar(select(func.count()).select_from(NewsItem)) == 1


async def test_automatic_and_explicit_analysis_enqueue_coalesce_atomically(session_factory):
    async with session_factory() as session:
        source = await add_source(session)
        data = collected()
        item_id = (await NewsItemRepository(session).ingest(source.id, [data], {}))["item_ids"][0]

    async def enqueue(key, force):
        async with session_factory() as session:
            return await NewsJobRepository(session).enqueue(
                "analyze", item_id=item_id, dedupe_key=key,
                payload={"content_hash": data["content_hash"], "force": force},
            )

    jobs = await asyncio.gather(
        enqueue(f"analysis:{item_id}:{data['content_hash']}:model:v1", False),
        enqueue(f"repair:17:{item_id}", True),
        enqueue(None, True),
    )
    assert len({job.id for job in jobs}) == 1
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(NewsJob)) == 1
        assert (await session.scalar(select(NewsJob))).payload["force"] is True


async def test_explicit_repair_restores_retained_text_even_when_hash_is_unchanged(db_session):
    source = await add_source(db_session)
    repo = NewsItemRepository(db_session)
    data = collected()
    item_id = (await repo.ingest(source.id, [data], {}))["item_ids"][0]
    original = await repo.get(item_id)
    original.content, original.excerpt = "", ""
    await db_session.commit()
    await repo.ingest(source.id, [data], {})
    assert (await repo.get(item_id)).content == ""
    result = await repo.ingest(source.id, [{**data, "existing_item_id": item_id}], {})
    repaired = await repo.get(item_id)
    assert repaired.content == data["content"] and repaired.content_hash == data["content_hash"]
    assert result["new"] == 0 and result["unchanged"] == 1


def observed_html(url, canonical=None, *, content="Useful source article text. " * 20, status="ready"):
    """Build the same normalized payload as the HTML adapter and enrichment path."""
    item = CollectedItem(
        None, normalize_url(url), normalize_url(canonical or url), "Stable article title",
        content=content, metadata={"method": "html", "collection_status": status},
    )
    return prepare_collected_item(item)


async def test_original_url_preserves_rbc_item_when_canonical_falls_back_after_fetch_failure(db_session):
    source = await add_source(db_session, url="https://trends.rbc.ru/")
    repo = NewsItemRepository(db_session)
    canonical = "https://trends.rbc.ru/trends/industry/67f2e8b59a79470abea1b719"
    original = canonical + "?from=mainpage"
    first = observed_html(original + "&utm_source=initial", canonical)
    item_id = (await repo.ingest(source.id, [first], {}))["item_ids"][0]
    analysis = await NewsAnalysisRepository(db_session).save(
        item_id, first["content_hash"], "model", "v1", analysis_data(),
    )
    decision = await NewsDecisionRepository(db_session).create(item_id, {
        "decision": "in_work", "format": "longread_candidate", "editor": "admin",
    })
    failed = observed_html(original, content="", status="fetch_failed")
    assert failed["normalized_url"] != first["normalized_url"]

    repeat = await repo.ingest(source.id, [failed], {}, collection_warning="Source fetch failed")

    assert repeat == {"new": 0, "updated": 0, "unchanged": 1, "item_ids": [item_id]}
    current = await repo.get(item_id)
    assert current.url == original
    assert current.canonical_url == current.normalized_url == canonical
    assert current.content_hash == first["content_hash"] and current.content == first["content"]
    assert current.latest_analysis_id == analysis.id and current.latest_decision_id == decision.id
    assert current.metadata_json["collection_warning"]
    assert await repo.known_urls(source.id) == {original, canonical}

    success = await repo.ingest(source.id, [first], {})
    assert success == {"new": 0, "updated": 0, "unchanged": 1, "item_ids": [item_id]}
    assert await db_session.scalar(select(func.count()).select_from(NewsItem)) == 1
    assert (await repo.get(item_id)).latest_analysis_id == analysis.id
    assert (await repo.get(item_id)).latest_decision_id == decision.id


async def test_previous_observed_url_remains_an_identity_after_another_alias_succeeds(db_session):
    source = await add_source(db_session)
    repo = NewsItemRepository(db_session)
    canonical = "https://example.org/article"
    first = observed_html(canonical + "?ref=first", canonical)
    second = observed_html(canonical + "?ref=second", canonical)
    item_id = (await repo.ingest(source.id, [first], {}))["item_ids"][0]
    assert (await repo.ingest(source.id, [second], {}))["item_ids"] == [item_id]
    assert (await repo.get(item_id)).url == second["url"]

    failed_first_alias = observed_html(first["url"], content="", status="fetch_failed")
    result = await repo.ingest(source.id, [failed_first_alias], {})

    assert result["new"] == 0 and result["item_ids"] == [item_id]
    assert (await repo.get(item_id)).normalized_url == canonical
    assert await repo.known_urls(source.id) == {canonical, first["url"], second["url"]}
    assert await db_session.scalar(select(func.count()).select_from(NewsItem)) == 1


@pytest.mark.parametrize("query", ["id", "from"])
async def test_meaningful_query_values_are_separate_source_identities(db_session, query):
    source = await add_source(db_session)
    repo = NewsItemRepository(db_session)
    first = observed_html(f"https://example.org/article?{query}=1")
    second = observed_html(f"https://example.org/article?{query}=2")
    created = await repo.ingest(source.id, [first, second], {})
    failed = [observed_html(row["url"], content="", status="fetch_failed") for row in (first, second)]

    repeated = await repo.ingest(source.id, failed, {})

    assert created["new"] == 2 and len(set(created["item_ids"])) == 2
    assert repeated["new"] == 0 and repeated["item_ids"] == created["item_ids"]
    assert await repo.known_urls(source.id) == {first["url"], second["url"]}
    assert await db_session.scalar(select(func.count()).select_from(NewsItem)) == 2


@pytest.mark.parametrize("explicit_repair", [False, True])
async def test_original_and_canonical_aliases_cannot_merge_different_records(db_session, explicit_repair):
    source = await add_source(db_session)
    source_id = source.id
    repo = NewsItemRepository(db_session)
    first = observed_html("https://example.org/first?view=source", "https://example.org/first")
    second = observed_html("https://example.org/second?view=source", "https://example.org/second")
    ids = (await repo.ingest(source_id, [first, second], {"pass": 1}))["item_ids"]
    newer_alias = observed_html("https://example.org/first?view=other", first["normalized_url"])
    await repo.ingest(source_id, [newer_alias], {"pass": 1})
    assert (await repo.get(ids[0])).url != first["url"]
    conflict = observed_html(first["url"], second["normalized_url"])
    if explicit_repair:
        conflict["existing_item_id"] = ids[0]

    with pytest.raises(NewsConflictError):
        await repo.ingest(source_id, [conflict], {"pass": 2})

    assert (await repo.get(ids[0])).normalized_url == first["normalized_url"]
    assert (await repo.get(ids[1])).normalized_url == second["normalized_url"]
    assert await db_session.scalar(select(func.count()).select_from(NewsItem)) == 2
    assert (await NewsSourceRepository(db_session).get(source_id)).cursor == {"pass": 1}


async def test_incoming_metadata_cannot_inject_source_url_aliases(db_session):
    source = await add_source(db_session)
    repo = NewsItemRepository(db_session)
    fake = "https://example.org/unrelated"
    first = observed_html("https://example.org/original", "https://example.org/article")
    first["metadata_json"]["source_url_aliases"] = [fake]
    item_id = (await repo.ingest(source.id, [first], {}))["item_ids"][0]
    assert fake not in await repo.known_urls(source.id)
    changed_alias = observed_html("https://example.org/changed", first["normalized_url"])
    changed_alias["metadata_json"]["source_url_aliases"] = [fake]
    await repo.ingest(source.id, [changed_alias], {})

    unrelated = await repo.ingest(source.id, [observed_html(fake)], {})

    assert unrelated["new"] == 1 and unrelated["item_ids"] != [item_id]
    stored_aliases = (await repo.get(item_id)).metadata_json["source_url_aliases"]
    assert set(stored_aliases) == {first["url"], changed_alias["url"]}


async def test_concurrent_fallback_ingestion_uses_the_same_stored_source_identity(session_factory):
    async with session_factory() as session:
        source = await add_source(session)
        good = observed_html("https://example.org/article?from=mainpage", "https://example.org/article")
        item_id = (await NewsItemRepository(session).ingest(source.id, [good], {}))["item_ids"][0]
        source_id = source.id

    async def ingest(data):
        async with session_factory() as session:
            return await NewsItemRepository(session).ingest(source_id, [data], {})

    failed = observed_html(good["url"], content="", status="fetch_failed")
    results = await asyncio.gather(ingest(failed), ingest(good), ingest(failed))

    assert all(row["new"] == 0 and row["item_ids"] == [item_id] for row in results)
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(NewsItem)) == 1
        assert (await NewsItemRepository(session).get(item_id)).normalized_url == good["normalized_url"]
