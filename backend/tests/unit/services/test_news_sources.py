"""External source behavior on controlled responses, without live websites."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from src.clients.news_http import NewsHttpResponse, PinnedPublicTransport, SafeNewsHttpClient, validate_public_url
from src.clients.news_sources import NEWS_MIN_CONTENT_CHARS, NewsSourceClient, normalize_url, prepare_collected_item
from src.exceptions.news_sources import NewsRobotsError, NewsSourceError, UnsafeNewsUrlError
from src.schemas.news_collection import CollectedItem

PUBLIC_IP = "93.184.216.34"


async def public_resolver(host: str, port: int) -> list[str]:
    return [PUBLIC_IP]


def document(content: str, *, status: int = 200, kind: str = "text/html", **headers) -> httpx.Response:
    return httpx.Response(status, content=content.encode(), headers={"Content-Type": kind, **headers})


def transport(handler, resolver=public_resolver):
    return PinnedPublicTransport(httpx.MockTransport(handler), resolver)


@pytest.mark.parametrize("url", [
    "file:///etc/passwd", "gopher://example.org/", "ftp://example.org/",
    "http://localhost", "http://LOCALHOST.", "http://backend", "http://db.internal",
    "http://127.0.0.1", "http://10.1.2.3", "http://172.30.55.10", "http://192.168.2.1",
    "http://169.254.169.254/latest/meta-data", "http://0.0.0.0", "http://[::1]",
    "http://[::ffff:127.0.0.1]", "http://[64:ff9b::7f00:1]", "http://2130706433",
    "https://user:secret@example.org/feed", "https://example.org:8080/", "https://example.org/\n",
])
def test_rejects_non_public_url_shapes(url):
    with pytest.raises(UnsafeNewsUrlError):
        validate_public_url(url)


def test_normalization_preserves_content_parameters():
    assert normalize_url("https://EXAMPLE.org:443/news?id=7&utm_source=x#title") == "https://example.org/news?id=7"
    assert normalize_url("https://example.org/news?id=7") != normalize_url("https://example.org/news?id=8")


@pytest.mark.parametrize("body", [b"/dev/zero", b".env", b"https://127.0.0.1/feed"])
def test_feed_body_cannot_be_interpreted_as_a_file_or_url(body, monkeypatch):
    file_open = Mock(side_effect=AssertionError("Feed data must not open a local file"))
    url_open = Mock(side_effect=AssertionError("Feed data must not perform network requests"))
    source = NewsSourceClient(AsyncMock(spec=SafeNewsHttpClient))
    with monkeypatch.context() as context:
        context.setattr("builtins.open", file_open)
        context.setattr("urllib.request.urlopen", url_open)
        with pytest.raises(NewsSourceError):
            source._parse_feed(body, "https://example.org/feed", 5)
    file_open.assert_not_called()
    url_open.assert_not_called()


@pytest.mark.asyncio
async def test_dns_pin_keeps_host_and_sni_and_strips_credentials():
    seen = []

    async def handler(request):
        seen.append(request)
        return document("ok")

    async with httpx.AsyncClient(transport=transport(handler)) as client:
        await client.get("https://example.org/news", headers={"Cookie": "private=x", "Authorization": "secret"})
    assert seen[0].url.host == PUBLIC_IP
    assert seen[0].headers["host"] == "example.org"
    assert seen[0].extensions["sni_hostname"] == "example.org"
    assert seen[0].headers["connection"] == "close"
    assert "cookie" not in seen[0].headers and "authorization" not in seen[0].headers


@pytest.mark.asyncio
async def test_mixed_dns_answers_are_blocked_before_connect():
    async def resolver(host, port):
        return [PUBLIC_IP, "127.0.0.1"]

    handler = AsyncMock(return_value=document("must not be reached"))
    async with httpx.AsyncClient(transport=transport(handler, resolver)) as client:
        with pytest.raises(UnsafeNewsUrlError):
            await client.get("https://example.org/feed")
    handler.assert_not_called()


@pytest.mark.asyncio
async def test_dns_is_rechecked_after_robots():
    addresses = iter([[PUBLIC_IP], ["169.254.169.254"]])
    calls = []

    async def resolver(host, port):
        return next(addresses)

    async def handler(request):
        calls.append(request.url.path)
        return document("User-agent: *\nAllow: /", kind="text/plain")

    async with httpx.AsyncClient(transport=transport(handler, resolver)) as client:
        safe = SafeNewsHttpClient(client, min_interval_seconds=0)
        with pytest.raises(UnsafeNewsUrlError):
            await safe.get("https://example.org/feed")
    assert calls == ["/robots.txt"]


@pytest.mark.asyncio
async def test_redirect_to_private_address_is_never_requested():
    calls = []

    async def handler(request):
        calls.append(request.url.path)
        if request.url.path == "/robots.txt":
            return document("", status=404)
        return document("", status=302, Location="http://127.0.0.1/admin")

    async with httpx.AsyncClient(transport=transport(handler)) as client:
        with pytest.raises(UnsafeNewsUrlError):
            await SafeNewsHttpClient(client, min_interval_seconds=0).get("https://example.org/feed")
    assert calls == ["/robots.txt", "/feed"]


@pytest.mark.asyncio
async def test_redirect_rechecks_destination_robots():
    calls = []

    async def handler(request):
        calls.append((request.headers["host"], request.url.path))
        if request.url.path == "/robots.txt":
            disallow = "/" if request.headers["host"] == "blocked.example.org" else ""
            return document(f"User-agent: *\nDisallow: {disallow}", kind="text/plain")
        return document("", status=302, Location="https://blocked.example.org/article")

    async with httpx.AsyncClient(transport=transport(handler)) as client:
        with pytest.raises(NewsRobotsError):
            await SafeNewsHttpClient(client, min_interval_seconds=0).get("https://example.org/feed")
    assert ("blocked.example.org", "/article") not in calls


@pytest.mark.asyncio
@pytest.mark.parametrize("result,code", [
    (document("x" * 1500), "response_too_large"),
    (document("{}", kind="application/json"), "content_type"),
])
async def test_response_bounds(result, code):
    async def handler(request):
        return document("", status=404) if request.url.path == "/robots.txt" else result

    async with httpx.AsyncClient(transport=transport(handler)) as client:
        with pytest.raises(NewsSourceError) as error:
            await SafeNewsHttpClient(client, max_response_bytes=1024, min_interval_seconds=0).get("https://example.org/feed")
    assert error.value.code == code


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [429, 500])
async def test_transient_status_has_bounded_retries(status, monkeypatch):
    monkeypatch.setattr("src.clients.news_http.asyncio.sleep", AsyncMock())
    attempts = 0

    async def handler(request):
        nonlocal attempts
        if request.url.path == "/robots.txt":
            return document("", status=404)
        attempts += 1
        return document("", status=status)

    async with httpx.AsyncClient(transport=transport(handler)) as client:
        with pytest.raises(NewsSourceError) as error:
            await SafeNewsHttpClient(client, retries=2, min_interval_seconds=0).get("https://example.org/feed")
    assert attempts == 2 and error.value.retryable


@pytest.mark.asyncio
async def test_timeout_is_a_safe_failure(monkeypatch):
    monkeypatch.setattr("src.clients.news_http.asyncio.sleep", AsyncMock())

    async def handler(request):
        raise httpx.ReadTimeout("secret response details", request=request)

    async with httpx.AsyncClient(transport=transport(handler)) as client:
        with pytest.raises(NewsSourceError) as error:
            await SafeNewsHttpClient(client, retries=2, min_interval_seconds=0).get("https://example.org/feed")
    assert "secret" not in str(error.value)


@pytest.mark.asyncio
async def test_rss_guid_fallback_content_and_conditional_not_modified():
    calls = []
    long_description = "Подробное описание разработки и доступности. " * 24
    feed = f'''<?xml version="1.0"?><rss version="2.0"><channel><title>News</title>
      <item><guid>https://example.org/article</guid><title>Статья</title>
      <description>{long_description}</description><pubDate>Thu, 08 Oct 2026 12:00:00 GMT</pubDate></item>
      <item><guid>https://example.org/article</guid><title>Дубль</title></item>
      </channel></rss>'''

    async def handler(request):
        calls.append(request)
        if request.url.path == "/robots.txt":
            return document("", status=404)
        if request.headers.get("if-none-match") == '"v1"':
            return document("", status=304)
        return document(feed, kind="application/rss+xml", ETag='"v1"', **{"Last-Modified": "Thu, 08 Oct 2026 12:00:00 GMT"})

    async with httpx.AsyncClient(transport=transport(handler)) as client:
        source = NewsSourceClient(SafeNewsHttpClient(client, min_interval_seconds=0))
        result = await source.fetch(url="https://example.org/feed", kind="rss", config={}, max_excerpt_chars=650)
        unchanged = await source.fetch(url="https://example.org/feed", kind="rss", config={}, etag=result.etag, last_modified=result.last_modified)
    assert len(result.items) == 1
    assert len(result.items[0].description) == 650
    assert result.items[0].external_id == "https://example.org/article"
    assert result.items[0].published_at == datetime(2026, 10, 8, 12, tzinfo=timezone.utc)
    assert result.items[0].updated_at is None
    assert result.items[0].metadata["collection_status"] == "ready"
    assert unchanged.not_modified and not unchanged.items
    assert not any(request.url.path == "/article" for request in calls)
    assert calls[-1].headers["if-modified-since"] == result.last_modified


@pytest.mark.asyncio
async def test_atom_discovery_from_html_alternate():
    async def handler(request):
        if request.url.path == "/robots.txt":
            return document("", status=404)
        if request.url.path == "/feed":
            return document('''<feed xmlns="http://www.w3.org/2005/Atom"><title>Feed</title>
              <entry><id>urn:news:1</id><title>Atom item</title><link href="/post"/>
              <updated>2026-10-08T12:30:00Z</updated></entry></feed>''', kind="application/atom+xml")
        return document('<html><head><link rel="alternate" type="application/atom+xml" href="/feed"></head><body><main></main></body></html>')

    async with httpx.AsyncClient(transport=transport(handler)) as client:
        result = await NewsSourceClient(SafeNewsHttpClient(client, min_interval_seconds=0)).discover("https://example.org/")
    assert result.kind == "rss" and result.url == "https://example.org/feed"
    assert result.items[0].url == "https://example.org/post"
    assert result.items[0].external_id == "urn:news:1"


@pytest.mark.asyncio
async def test_html_selectors_clean_markup_and_reject_bad_selector():
    html = '''<main><div class="story"><h2><a href="/post?utm_source=rss">Новая библиотека</a></h2>
      <time datetime="2026-10-08T10:00:00Z"></time><p class="intro">Текст <script>evil()</script> описания</p></div></main>'''

    async def handler(request):
        return document("", status=404) if request.url.path == "/robots.txt" else document(html)

    async with httpx.AsyncClient(transport=transport(handler)) as client:
        source = NewsSourceClient(SafeNewsHttpClient(client, min_interval_seconds=0))
        result = await source.discover("https://example.org", "html", {"item_selector": ".story", "content_selector": ".intro"})
        with pytest.raises(NewsSourceError) as error:
            await source.discover("https://example.org", "html", {"item_selector": "[broken"})
    assert result.items[0].description == "Текст описания"
    assert result.items[0].url == "https://example.org/post"
    assert error.value.code == "invalid_selector"


@pytest.mark.asyncio
async def test_first_run_age_limit_and_missing_date():
    feed = '''<rss version="2.0"><channel><title>News</title>
      <item><guid>old</guid><link>https://example.org/old</link><title>Old</title><pubDate>01 Jan 2000 00:00:00 GMT</pubDate></item>
      <item><guid>undated</guid><link>https://example.org/undated</link><title>Undated</title></item>
      </channel></rss>'''

    async def handler(request):
        if request.url.path == "/feed":
            return document(feed, kind="application/rss+xml")
        return document("", status=404)

    async with httpx.AsyncClient(transport=transport(handler)) as client:
        result = await NewsSourceClient(SafeNewsHttpClient(client, min_interval_seconds=0)).fetch(
            url="https://example.org/feed", kind="rss", config={}, first_run=True, max_items=1,
        )
    assert [item.external_id for item in result.items] == ["undated"]


@pytest.mark.asyncio
async def test_first_html_run_applies_age_before_item_limit():
    current = datetime.now(timezone.utc).isoformat()
    html = f'''<main><article><a href="/old">Old</a><time datetime="1970-01-01"></time></article>
      <article><a href="/new">Recent</a><time datetime="{current}"></time><p>{'Useful text ' * 100}</p></article></main>'''

    async def handler(request):
        return document("", status=404) if request.url.path == "/robots.txt" else document(html)

    async with httpx.AsyncClient(transport=transport(handler)) as client:
        result = await NewsSourceClient(SafeNewsHttpClient(client, min_interval_seconds=0)).fetch(
            url="https://example.org/news", kind="html", config={}, first_run=True, max_items=1,
        )
    assert [item.title for item in result.items] == ["Recent"]


@pytest.mark.asyncio
async def test_article_enrichment_canonical_and_stable_hash():
    feed = '''<rss version="2.0"><channel><title>News</title><item><guid>x</guid>
      <link>https://example.org/post?utm_source=rss</link><title>Title</title><description>Short</description>
      </item></channel></rss>'''

    async def handler(request):
        if request.url.path == "/robots.txt":
            return document("", status=404)
        if request.url.path == "/feed":
            return document(feed, kind="application/rss+xml")
        return document('<link rel="canonical" href="https://example.org/canonical"><nav>Menu</nav><article><h1>Title</h1><p>Useful article text</p><aside>Advertisement</aside></article>')

    async with httpx.AsyncClient(transport=transport(handler)) as client:
        source = NewsSourceClient(SafeNewsHttpClient(client, min_interval_seconds=0))
        first = await source.fetch(url="https://example.org/feed", kind="rss", config={})
        second = await source.fetch(url="https://example.org/feed", kind="rss", config={})
    data = prepare_collected_item(first.items[0])
    assert data["normalized_url"] == "https://example.org/canonical"
    assert data["content"] == "Title Useful article text"
    assert data["content_hash"] == prepare_collected_item(second.items[0])["content_hash"]


@pytest.mark.asyncio
async def test_explicit_cutoff_also_limits_repeat_collection_before_item_limit():
    description = "Detailed source description. " * 30
    feed = f'''<rss version="2.0"><channel><title>News</title>
      <item><guid>old</guid><link>https://example.org/old</link><title>Old</title>
        <pubDate>01 Jan 2000 00:00:00 GMT</pubDate><description>{description}</description></item>
      <item><guid>new</guid><link>https://example.org/new</link><title>Recent</title>
        <pubDate>13 Oct 2026 00:00:00 GMT</pubDate><description>{description}</description></item>
      </channel></rss>'''

    async def handler(request):
        return document("", status=404) if request.url.path == "/robots.txt" else document(feed, kind="application/rss+xml")

    async with httpx.AsyncClient(transport=transport(handler)) as client:
        source = NewsSourceClient(SafeNewsHttpClient(client, min_interval_seconds=0))
        result = await source.fetch(
            url="https://example.org/feed", kind="rss", config={}, first_run=False,
            max_items=1, cutoff=datetime(2026, 9, 14, tzinfo=timezone.utc),
        )
    assert [item.external_id for item in result.items] == ["new"]


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["rss", "html"])
async def test_cutoff_keeps_known_old_publications_for_content_repairs(kind):
    description = "Detailed source description. " * 30
    feed = f'''<rss version="2.0"><channel><title>News</title>
      <item><link>https://example.org/unknown</link><title>Unknown archive</title>
        <pubDate>01 Jan 2000 00:00:00 GMT</pubDate><description>{description}</description></item>
      <item><link>https://example.org/known?utm_source=feed</link><title>Known archive</title>
        <pubDate>01 Jan 2000 00:00:00 GMT</pubDate><description>{description}</description></item>
      </channel></rss>'''
    html = f'''<main><article><h2><a href="/unknown">Unknown archive</a></h2>
      <time datetime="2000-01-01"></time><p>{description}</p></article>
      <article><h2><a href="/known?utm_source=feed">Known archive</a></h2>
      <time datetime="2000-01-01"></time><p>{description}</p></article></main>'''

    async def handler(request):
        if request.url.path == "/robots.txt":
            return document("", status=404)
        return document(feed, kind="application/rss+xml") if kind == "rss" else document(html)

    async with httpx.AsyncClient(transport=transport(handler)) as client:
        result = await NewsSourceClient(SafeNewsHttpClient(client, min_interval_seconds=0)).fetch(
            url="https://example.org/feed", kind=kind, config={}, max_items=1,
            cutoff=datetime(2026, 9, 14, tzinfo=timezone.utc), known_urls={"https://example.org/known"},
        )
    assert [item.url for item in result.items] == ["https://example.org/known"]


@pytest.mark.parametrize("container", [
    '<div class="blog-content">{content}</div>',
    '<div itemprop="articleBody">{content}</div>',
    '<article>{content}</article>',
    '{content}',
])
def test_article_ignores_navigation_cards_and_dynamic_controls(container):
    paragraph = "The technical article explains training, evaluation and deployment. " * 12
    controls = '<button>Downloads 100 Likes 50</button><div class="share-buttons">Share 500</div>'
    content = container.format(content=f"<p>{paragraph}</p>{controls}")
    html = f'''<html><head><link rel="canonical" href="/canonical"></head><body>
      <nav><article class="overview-card-wrapper group/repo">Model downloads 123</article></nav>
      <aside><article>{'Sidebar repository metadata ' * 100}</article></aside>
      <header><article>Trending models</article></header>
      <footer><article>Footer recommendations</article></footer>
      <div role="navigation"><article>{'Navigation ' * 100}</article></div>
      <main>{content}</main></body></html>'''
    source = NewsSourceClient(AsyncMock(spec=SafeNewsHttpClient))
    canonical, extracted = source._article(NewsHttpResponse(
        "https://example.org/post", 200, html.encode(), httpx.Headers(),
    ))
    assert canonical == "https://example.org/canonical"
    assert extracted == paragraph.strip()


def test_short_article_card_does_not_hide_substantial_main_content():
    paragraph = "Actual publication body describing a software architecture. " * 12
    html = f'<article>Small recommendation card</article><main><p>{paragraph}</p></main>'
    source = NewsSourceClient(AsyncMock(spec=SafeNewsHttpClient))
    _, extracted = source._article(NewsHttpResponse("https://example.org/post", 200, html.encode(), httpx.Headers()))
    assert extracted == paragraph.strip()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure,status", [("request", "fetch_failed"), ("empty_layout", "insufficient_text")])
async def test_failed_repeat_enrichment_records_quality_and_keeps_source_metadata(failure, status):
    feed = '''<rss version="2.0"><channel><title>News</title><language>en</language>
      <item><guid>stable</guid><link>https://example.org/post</link><title>Stable title</title>
        <pubDate>13 Oct 2026 00:00:00 GMT</pubDate><description>Short RSS description</description>
      </item></channel></rss>'''
    failing = False

    async def handler(request):
        if request.url.path == "/robots.txt":
            return document("", status=404)
        if request.url.path == "/feed":
            return document(feed, kind="application/rss+xml")
        if failing:
            return document("", status=403) if failure == "request" else document("<body>Unrecognized layout</body>")
        return document("<article><p>" + "Meaningful article content. " * 80 + "</p></article>")

    async with httpx.AsyncClient(transport=transport(handler)) as client:
        source = NewsSourceClient(SafeNewsHttpClient(client, min_interval_seconds=0))
        first = await source.fetch(url="https://example.org/feed", kind="rss", config={})
        failing = True
        second = await source.fetch(url="https://example.org/feed", kind="rss", config={})
    assert first.items[0].metadata["collection_status"] == "ready"
    assert len(first.items[0].content) > NEWS_MIN_CONTENT_CHARS
    observed = second.items[0]
    assert observed.content == observed.description == "Short RSS description"
    assert observed.metadata["collection_status"] == status
    assert observed.metadata["collection_warning"] in second.warnings
    assert observed.metadata["language"] == "en"
    assert observed.metadata["method"] == "rss"
    assert observed.published_at == first.items[0].published_at
    assert observed.external_id == first.items[0].external_id
    assert prepare_collected_item(observed)["metadata_json"]["collection_status"] == status


@pytest.mark.asyncio
@pytest.mark.parametrize("length,status", [(NEWS_MIN_CONTENT_CHARS - 1, "insufficient_text"), (NEWS_MIN_CONTENT_CHARS, "ready")])
async def test_enrichment_requires_minimum_cleaned_text(length, status):
    text = ("The publication explains a technical approach. " * 10)[:length - 1] + "."
    feed = '''<rss version="2.0"><channel><title>News</title>
      <item><link>https://example.org/post</link><title>Title</title></item></channel></rss>'''

    async def handler(request):
        if request.url.path == "/robots.txt":
            return document("", status=404)
        return document(feed, kind="application/rss+xml") if request.url.path == "/feed" else document(f"<main><p>{text}</p></main>")

    async with httpx.AsyncClient(transport=transport(handler)) as client:
        result = await NewsSourceClient(SafeNewsHttpClient(client, min_interval_seconds=0)).fetch(
            url="https://example.org/feed", kind="rss", config={},
        )
    assert len(result.items[0].content) == length
    assert result.items[0].metadata["collection_status"] == status
    assert bool(result.warnings) == (status == "insufficient_text")


@pytest.mark.asyncio
@pytest.mark.parametrize("failed", [False, True])
async def test_refetch_always_loads_article_and_does_not_reuse_previous_text(failed):
    old_text = "Previous article fragment. " * 100
    new_text = "Fresh article body from the source. " * 40
    published = datetime(2026, 10, 13, tzinfo=timezone.utc)
    item = CollectedItem(
        "stable-guid", "https://example.org/post", "https://example.org/post", "Stable title",
        old_text, old_text, published, published,
        {"language": "en", "method": "rss", "collection_status": "insufficient_text", "collection_warning": "Old warning"},
    )
    requested = []

    async def handler(request):
        requested.append(request.url.path)
        if request.url.path == "/robots.txt":
            return document("", status=404)
        return document("", status=403) if failed else document(f'<main><div class="blog-content"><p>{new_text}</p></div></main>')

    async with httpx.AsyncClient(transport=transport(handler)) as client:
        result = await NewsSourceClient(SafeNewsHttpClient(client, min_interval_seconds=0)).refetch([item])
    assert requested.count("/post") == 1
    refreshed = result.items[0]
    assert refreshed.title == item.title
    assert refreshed.external_id == item.external_id
    assert refreshed.published_at == refreshed.updated_at == published
    assert refreshed.metadata["language"] == "en"
    assert refreshed.metadata["method"] == "rss"
    assert refreshed.description == ""
    assert refreshed.content == ("" if failed else new_text.strip())
    assert refreshed.metadata["collection_status"] == ("fetch_failed" if failed else "ready")
    if failed:
        assert refreshed.metadata["collection_warning"] in result.warnings
    else:
        assert "collection_warning" not in refreshed.metadata
        assert result.warnings == []
    assert item.content == item.description == old_text


@pytest.mark.asyncio
async def test_xml_entities_are_not_parsed():
    async def handler(request):
        if request.url.path == "/robots.txt":
            return document("", status=404)
        return document('<!DOCTYPE rss [<!ENTITY x SYSTEM "file:///etc/passwd">]><rss version="2.0"><channel>&x;</channel></rss>', kind="application/rss+xml")

    async with httpx.AsyncClient(transport=transport(handler)) as client:
        with pytest.raises(NewsSourceError) as error:
            await NewsSourceClient(SafeNewsHttpClient(client, min_interval_seconds=0)).discover("https://example.org/feed", "rss")
    assert error.value.code == "unsafe_xml"
