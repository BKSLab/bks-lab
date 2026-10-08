"""External source behavior on controlled responses, without live websites."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from src.clients.news_http import PinnedPublicTransport, SafeNewsHttpClient, validate_public_url
from src.clients.news_sources import NewsSourceClient, normalize_url, prepare_collected_item
from src.exceptions.news_sources import NewsRobotsError, NewsSourceError, UnsafeNewsUrlError

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
async def test_xml_entities_are_not_parsed():
    async def handler(request):
        if request.url.path == "/robots.txt":
            return document("", status=404)
        return document('<!DOCTYPE rss [<!ENTITY x SYSTEM "file:///etc/passwd">]><rss version="2.0"><channel>&x;</channel></rss>', kind="application/rss+xml")

    async with httpx.AsyncClient(transport=transport(handler)) as client:
        with pytest.raises(NewsSourceError) as error:
            await NewsSourceClient(SafeNewsHttpClient(client, min_interval_seconds=0)).discover("https://example.org/feed", "rss")
    assert error.value.code == "unsafe_xml"
