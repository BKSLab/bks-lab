"""Audit coverage, extraction quality and repeated observations on controlled clients."""

import argparse
import asyncio
from contextlib import asynccontextmanager
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from scripts import audit_news_catalogue
from scripts.audit_news_catalogue import audit_targets, collection_result, compare_collections, read_catalogue
from src.clients.news_http import SafeNewsHttpClient
from src.clients.news_sources import NewsSourceClient
from src.exceptions.news_sources import NewsSourceError
from src.schemas.news_collection import CollectedItem, CollectionResult, DiscoveryResult


def publication(path="one", content="Useful technical source content. " * 20, **metadata):
    url = f"https://example.org/{path}"
    return CollectedItem(path, url, url, "Publication title", content=content, metadata=metadata)


@pytest.fixture
def mocked_audit(monkeypatch):
    source = Mock(spec=NewsSourceClient)
    source.discover = AsyncMock(spec=NewsSourceClient.discover, return_value=DiscoveryResult(
        "rss", "https://example.org/feed", [publication()],
    ))
    source.fetch = AsyncMock(spec=NewsSourceClient.fetch)
    source.http = SimpleNamespace(
        client=SimpleNamespace(event_hooks={"response": []}),
        get=AsyncMock(spec=SafeNewsHttpClient.get),
    )

    @asynccontextmanager
    async def client_context(settings):
        yield source

    monkeypatch.setattr(audit_news_catalogue, "news_source_client", client_context)
    monkeypatch.setattr(audit_news_catalogue, "NewsSettings", lambda: SimpleNamespace(
        http_timeout_seconds=20, http_max_response_bytes=2 * 1024 * 1024, http_max_redirects=5,
    ))
    args = argparse.Namespace(
        only=None, concurrency=1, documents_dir=None, timeout=1, collect=True, repeat_collect=True,
    )
    entries = [{"id": "example", "url": "https://example.org/feed", "mode": "rss"}]
    return source, args, entries


@pytest.mark.parametrize("prefix,suffix", [
    ("", ""),
    ("\ufeffexport const sourceCatalogue: SourceCatalogueEntry[] = ", ";\n"),
])
def test_reads_json_and_typescript_catalogues(prefix: str, suffix: str) -> None:
    entries = read_catalogue(prefix + '[{"id":"source","url":"https://example.org/"}]' + suffix)
    assert entries == [{"id": "source", "url": "https://example.org/"}]


def test_covers_homepages_feeds_extras_and_duplicate_rows() -> None:
    entries = [
        {"id": "author", "url": "https://example.org/", "feedUrl": "https://example.org/feed",
         "mode": "rss", "extraUrls": ["https://example.org/all"]},
        {"id": "engineering", "url": "https://example.org/", "feedUrl": "https://example.org/feed",
         "mode": "rss", "extraUrls": []},
        {"id": "api", "url": "https://api.example.org/", "mode": "api",
         "extraUrls": ["https://api.example.org/search"]},
        {"id": "archive", "url": "https://archive.example.org/", "mode": "read", "extraUrls": []},
    ]
    targets = {row["url"]: row for row in audit_targets(entries)}
    assert len(targets) == 6
    assert targets["https://example.org/feed"]["primary_ids"] == ["author", "engineering"]
    assert targets["https://example.org/feed"]["kind"] == "rss"
    assert targets["https://example.org/"]["primary_ids"] == []
    assert targets["https://example.org/"]["kind"] is None
    assert targets["https://example.org/all"]["discover"] is True
    assert targets["https://api.example.org/"]["discover"] is False
    assert targets["https://api.example.org/search"]["discover"] is False
    assert targets["https://archive.example.org/"]["discover"] is False


async def test_repeat_collect_is_unconditional_and_reuses_cutoff_with_first_known_urls(mocked_audit):
    source, args, entries = mocked_audit
    first_item = replace(publication(), url="https://example.org/original?utm_source=feed")
    second_item = replace(first_item, canonical_url="https://example.org/one?utm_source=other")
    source.fetch.side_effect = [
        CollectionResult([first_item], etag='"v1"', last_modified="Yesterday"),
        CollectionResult([second_item]),
    ]

    report = await audit_news_catalogue.audit(args, entries)

    first_call, second_call = [call.kwargs for call in source.fetch.await_args_list]
    assert first_call["cutoff"] == second_call["cutoff"]
    assert first_call["known_urls"] == set()
    assert second_call["known_urls"] == {"https://example.org/original", "https://example.org/one"}
    for call in (first_call, second_call):
        assert call["max_items"] == 3
        assert call["url"] == "https://example.org/feed"
        assert not call.get("etag") and not call.get("last_modified")
    row = report["results"][0]
    assert row["status"] == "preview"
    assert row["collection"]["status"] == row["repeat_collection"]["status"] == "passed"
    assert row["comparison"]["status"] == "compared"
    assert row["comparison"]["unchanged"] == 1
    assert row["comparison"]["changed"] == row["comparison"]["new"] == row["comparison"]["disappeared"] == 0
    assert report["summary"] == {"preview": 1}
    assert report["collection_summary"]["first"]["quality"]["ready"] == 1


def test_equal_hash_observations_collapse_by_normalized_identity():
    item = publication()
    tracked = replace(item, canonical_url=item.canonical_url + "?utm_source=again#fragment")
    comparison = compare_collections(CollectionResult([item, tracked]), CollectionResult([tracked]))
    assert comparison["common"] == comparison["unchanged"] == 1
    assert comparison["changed"] == comparison["new"] == comparison["disappeared"] == 0
    assert comparison["repeated_identities"] == {"first": 1, "repeat": 0}
    assert comparison["collision_urls"] == []


async def test_shared_canonical_for_different_urls_marks_comparison_ambiguous(mocked_audit):
    source, args, entries = mocked_audit
    first = publication()
    other = replace(publication("other"), canonical_url=first.canonical_url + "?utm_source=site")
    source.fetch.side_effect = [CollectionResult([first, other]), CollectionResult([first, other])]

    report = await audit_news_catalogue.audit(args, entries)

    row = report["results"][0]
    for field in ("collection", "repeat_collection"):
        assert row[field]["status"] == "degraded"
        assert row[field]["repeated_identities"] == 1
        assert row[field]["collision_urls"] == [first.canonical_url]
        assert row[field]["warnings"]
    assert row["comparison"]["status"] == "ambiguous"
    assert row["comparison"]["collision_urls"] == [first.canonical_url]
    assert row["comparison"]["warnings"]
    assert report["collection_summary"]["first"]["collisions"] == 1


def test_collection_quality_counts_statuses_and_deduplicates_warnings():
    warning = "Safe extraction warning"
    batch = CollectionResult([
        publication("ready", collection_status="ready"),
        publication("failed", content="", collection_status="fetch_failed", collection_warning=warning),
        publication("short", content="Short source card", collection_status="insufficient_text", collection_warning=warning),
    ], warnings=[warning])
    result = collection_result(batch)
    assert result["status"] == "degraded"
    assert result["quality"] == {"ready": 1, "fetch_failed": 1, "insufficient_text": 1}
    assert result["warnings"] == [warning]


def test_changed_hash_and_new_or_missing_urls_are_separate_observations():
    original = publication()
    updated = replace(original, content="Updated technical explanation. " * 20)
    comparison = compare_collections(
        CollectionResult([original, publication("removed")]),
        CollectionResult([updated, publication("new")]),
    )
    assert comparison["status"] == "compared"
    assert comparison["changed_urls"] == [original.canonical_url]
    assert comparison["new_urls"] == ["https://example.org/new"]
    assert comparison["disappeared_urls"] == ["https://example.org/removed"]
    assert comparison["changed"] == comparison["new"] == comparison["disappeared"] == 1
    assert comparison["unchanged"] == 0


async def test_repeat_can_recover_failed_text_without_hiding_first_pass_quality(mocked_audit):
    source, args, entries = mocked_audit
    warning = "Не удалось получить текст страницы; сохранена карточка источника."
    source.fetch.side_effect = [
        CollectionResult([publication(content="", collection_status="fetch_failed", collection_warning=warning)]),
        CollectionResult([publication(collection_status="ready")]),
    ]

    report = await audit_news_catalogue.audit(args, entries)

    row = report["results"][0]
    assert row["collection"]["status"] == "degraded"
    assert row["collection"]["warnings"] == [warning]
    assert row["repeat_collection"]["status"] == "passed"
    assert row["comparison"]["changed"] == 1
    assert report["collection_summary"]["first"]["statuses"] == {"degraded": 1}
    assert report["collection_summary"]["first"]["quality"]["fetch_failed"] == 1
    assert report["collection_summary"]["repeat"]["statuses"] == {"passed": 1}
    assert report["collection_summary"]["comparison"]["changed"] == 1


@pytest.mark.parametrize("batch,status", [
    (CollectionResult([]), "empty"),
    (CollectionResult([], not_modified=True), "not_modified"),
    (CollectionResult([publication(content="Short card", collection_status="ready")]), "degraded"),
    (CollectionResult([publication()], warnings=["Source warning"]), "degraded"),
])
async def test_empty_short_not_modified_and_warning_batches_are_not_passed(mocked_audit, batch, status):
    source, args, entries = mocked_audit
    args.repeat_collect = False
    source.fetch.return_value = batch

    report = await audit_news_catalogue.audit(args, entries)

    assert report["results"][0]["collection"]["status"] == status
    assert report["collection_summary"]["first"]["statuses"] == {status: 1}
    assert report["collection_summary"]["repeat"]["statuses"] == {}


async def test_not_modified_second_pass_does_not_claim_items_disappeared(mocked_audit):
    source, args, entries = mocked_audit
    source.fetch.side_effect = [CollectionResult([publication()]), CollectionResult([], not_modified=True)]

    report = await audit_news_catalogue.audit(args, entries)

    row = report["results"][0]
    assert row["repeat_collection"]["status"] == "not_modified"
    assert row["comparison"] == {"status": "unavailable", "reason": "not_modified"}


async def test_first_collection_error_does_not_prevent_second_observation(mocked_audit):
    source, args, entries = mocked_audit
    source.fetch.side_effect = [NewsSourceError("http_unavailable", "Safe source failure"), CollectionResult([publication()])]

    report = await audit_news_catalogue.audit(args, entries)

    row = report["results"][0]
    assert row["status"] == "preview"
    assert row["collection"]["status"] == "failed"
    assert row["repeat_collection"]["status"] == "passed"
    assert row["comparison"] == {"status": "unavailable", "reason": "collection_failed"}


async def test_repeat_timeout_preserves_first_collection_and_discovery(mocked_audit):
    source, args, entries = mocked_audit
    args.timeout = 0.05
    calls = 0

    async def collect(**kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return CollectionResult([publication()])
        await asyncio.sleep(1)

    source.fetch.side_effect = collect
    report = await audit_news_catalogue.audit(args, entries)

    row = report["results"][0]
    assert row["status"] == "preview"
    assert row["collection"]["status"] == "passed"
    assert row["repeat_collection"]["error_code"] == "audit_timeout"
    assert row["comparison"]["status"] == "unavailable"
    assert report["collection_summary"]["repeat"]["statuses"] == {"failed": 1}


def test_repeat_collect_requires_collect(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["audit-news", "--catalogue", "-", "--output", "unused.json", "--repeat-collect"])
    with pytest.raises(SystemExit) as error:
        audit_news_catalogue.main()
    assert error.value.code == 2
    assert "--repeat-collect requires --collect" in capsys.readouterr().err
