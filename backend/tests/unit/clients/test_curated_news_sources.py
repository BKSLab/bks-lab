"""Replay sanitized publisher layouts through supported collection adapters."""

import json
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest
from bs4 import BeautifulSoup

from src.clients.news_http import SafeNewsHttpClient
from src.clients.news_sources import NewsSourceClient, prepare_collected_item
from src.exceptions.news_sources import NewsSourceError
from src.core.news_source_schedule import validate_source_schedule
from src.news_sources import get_source_profile, get_source_profiles

BACKEND = Path(__file__).resolve().parents[3]


def test_profiles_are_unique_frozen_and_have_verification_evidence() -> None:
    profiles = get_source_profiles()
    assert profiles
    for field in ("id", "slug", "url"):
        assert len({getattr(profile, field) for profile in profiles}) == len(profiles)
    for profile in profiles:
        assert get_source_profile(profile.id) is profile
        assert profile.article_selectors
        assert profile.verification_method == "safe-http-list-article-repeat"
        validate_source_schedule(profile.default_schedule)
        assert (BACKEND / profile.fixture_path).is_file()
        if profile.kind == "html":
            assert profile.config["item_selector"]
            assert profile.config["title_selector"]
        with pytest.raises(FrozenInstanceError):
            profile.url = "https://untrusted.example/feed"
    assert get_source_profile("unknown-source") is None


def test_profile_cache_version_tracks_collection_rules_only() -> None:
    profile = get_source_profiles()[0]
    assert replace(profile, name="Display name", default_schedule={"mode": "daily", "times": ["10:00"]}).version == profile.version
    assert replace(profile, article_selectors=(".changed-layout",)).version != profile.version
    assert replace(profile, config={"item_selector": ".changed-list"}).version != profile.version


async def test_unknown_source_fails_before_any_network_request() -> None:
    http = AsyncMock(spec=SafeNewsHttpClient)
    source = NewsSourceClient(http)
    with pytest.raises(NewsSourceError, match="не поддерживается") as caught:
        await source.fetch_profile("not-a-supported-source")
    assert caught.value.code == "unsupported_source"
    http.get.assert_not_awaited()
    with pytest.raises(NewsSourceError):
        await source.refetch([], profile_id="not-a-supported-source")
    http.get.assert_not_awaited()


@pytest.mark.parametrize("profile", get_source_profiles(), ids=lambda profile: profile.id)
async def test_source_layout_article_text_and_repeated_collection(profile) -> None:
    fixture = json.loads((BACKEND / profile.fixture_path).read_text(encoding="utf-8"))
    assert fixture["profile_id"] == profile.id
    documents = {fixture["listing"]["url"]: fixture["listing"]}
    documents.update({article["url"]: article for article in fixture["articles"]})
    variant = 0
    requested: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        requested.append(url)
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /", headers={"Content-Type": "text/plain"})
        assert url in documents, f"Unexpected source URL: {url}"
        document = documents[url]
        body = document["body"].replace("fixture-noise-a", f"fixture-noise-{variant}")
        return httpx.Response(200, text=body, headers={"Content-Type": document["content_type"]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle), trust_env=False) as client:
        source = NewsSourceClient(SafeNewsHttpClient(client, min_interval_seconds=0))
        first = await source.fetch_profile(profile.id, max_items=3)
        first_articles = await source.refetch(first.items, profile_id=profile.id)
        variant = 1
        second = await source.fetch_profile(profile.id, max_items=3)
        second_articles = await source.refetch(second.items, profile_id=profile.id)

    expected = fixture["expected_urls"]
    assert [item.url for item in first.items] == [item.url for item in second.items] == expected
    assert expected
    assert not first.warnings and not first_articles.warnings
    assert not second.warnings and not second_articles.warnings
    for batch in (first_articles, second_articles):
        for item in batch.items:
            assert item.metadata["collection_status"] == "ready"
            assert "Fixture article" in item.content
            assert "fixture-noise" not in item.content
            assert len(item.content) >= 200
    before = [prepare_collected_item(item) for item in first_articles.items]
    after = [prepare_collected_item(item) for item in second_articles.items]
    assert [(item["normalized_url"], item["content_hash"]) for item in before] == [
        (item["normalized_url"], item["content_hash"]) for item in after
    ]
    assert len({item["normalized_url"] for item in before}) == len(expected)
    assert set(expected).issubset(set(requested))


async def test_profile_html_does_not_accept_a_long_teaser_when_article_layout_breaks() -> None:
    profile = next(profile for profile in get_source_profiles() if profile.kind == "html")
    fixture = json.loads((BACKEND / profile.fixture_path).read_text(encoding="utf-8"))
    listing = BeautifulSoup(fixture["listing"]["body"], "html.parser")
    card = listing.select_one(profile.config["item_selector"])
    teaser = card.select_one("p")
    if teaser is None:
        teaser = listing.new_tag("p")
        card.append(teaser)
    teaser.clear()
    teaser.append("Long source card description. " * 60)

    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /", headers={"Content-Type": "text/plain"})
        if str(request.url) == fixture["listing"]["url"]:
            body = str(listing)
        else:
            body = "<main><h1>Navigation page</h1><p>" + "Unrelated menu text. " * 60 + "</p></main>"
        return httpx.Response(200, text=body, headers={"Content-Type": "text/html"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle), trust_env=False) as client:
        source = NewsSourceClient(SafeNewsHttpClient(client, min_interval_seconds=0))
        batch = await source.fetch_profile(profile.id, max_items=1)

    assert batch.items[0].metadata["collection_status"] == "insufficient_text"
    assert batch.warnings
