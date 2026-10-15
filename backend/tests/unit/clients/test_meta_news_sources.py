"""Regressions for Meta's featured cards, publication dates and article layouts."""

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest

from src.clients.news_http import NewsHttpResponse, SafeNewsHttpClient
from src.clients.news_sources import NewsSourceClient, prepare_collected_item
from src.news_sources.labs_meta import PROFILE


@pytest.fixture
def meta_fixture() -> dict:
    path = Path(__file__).resolve().parents[3] / PROFILE.fixture_path
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
async def meta_source(meta_fixture: dict) -> AsyncIterator[NewsSourceClient]:
    documents = {document["url"]: document for document in [
        meta_fixture["listing"], *meta_fixture["articles"],
    ]}

    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /", headers={"Content-Type": "text/plain"})
        document = documents[str(request.url)]
        return httpx.Response(200, text=document["body"], headers={"Content-Type": document["content_type"]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle), trust_env=False) as client:
        yield NewsSourceClient(SafeNewsHttpClient(client, min_interval_seconds=0))


async def test_meta_reads_headlines_dates_and_brain_text_without_duplicate_badges(
    meta_source: NewsSourceClient, meta_fixture: dict,
) -> None:
    first = await meta_source.fetch_profile(PROFILE.id)
    second = await meta_source.fetch_profile(PROFILE.id)

    assert not first.warnings and not second.warnings
    assert [item.url for item in first.items] == [article["url"] for article in meta_fixture["articles"]]
    assert [item.title for item in first.items] == [f"Fixture publication {number}" for number in range(1, 6)]
    assert [item.published_at for item in first.items] == [
        datetime(2026, 7, 9, tzinfo=UTC), datetime(2026, 7, 27, tzinfo=UTC),
        datetime(2026, 7, 21, tzinfo=UTC), datetime(2026, 7, 7, tzinfo=UTC),
        datetime(2026, 6, 29, tzinfo=UTC),
    ]
    for item in first.items:
        assert item.metadata["collection_status"] == "ready"
        assert len(item.content) >= 200
        assert "Fixture article" in item.content
        assert "fixture-noise" not in item.content
    assert "brain2qwerty" in first.items[-1].url
    assert [prepare_collected_item(item)["content_hash"] for item in first.items] == [
        prepare_collected_item(item)["content_hash"] for item in second.items
    ]


async def test_meta_skips_old_unknown_publications_but_refreshes_existing_cards(
    meta_source: NewsSourceClient, meta_fixture: dict,
) -> None:
    cutoff = datetime(2026, 10, 15, tzinfo=UTC)
    initial = await meta_source.fetch_profile(PROFILE.id, cutoff=cutoff)
    assert not initial.items and not initial.warnings
    assert len(initial.skipped) == 5

    known_urls = {article["url"] for article in meta_fixture["articles"]}
    repaired = await meta_source.fetch_profile(PROFILE.id, cutoff=cutoff, known_urls=known_urls)
    assert {item.url for item in repaired.items} == known_urls
    assert all(item.published_at is not None for item in repaired.items)
    assert not repaired.warnings


def test_meta_does_not_use_navigation_or_an_unrecognized_body_as_article_text() -> None:
    noise = "Unrelated navigation text. " * 40
    body = (
        '<html><body><nav><div class="_9bhp"><p class="_a92o _a5c- _a5w7">'
        + noise + '</p></div></nav><main><p>' + noise + '</p></main></body></html>'
    )
    response = NewsHttpResponse(PROFILE.url + "unknown/", 200, body.encode(), httpx.Headers())
    adapter = NewsSourceClient(AsyncMock(spec=SafeNewsHttpClient), profile=PROFILE)
    assert adapter._article(response) == (None, "")
