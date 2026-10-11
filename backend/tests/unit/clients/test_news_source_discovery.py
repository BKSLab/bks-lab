"""Synthetic regressions for public HTML layouts observed in the source catalogue."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import httpx
import pytest

from src.clients.news_http import PinnedPublicTransport, SafeNewsHttpClient
from src.clients.news_sources import NewsSourceClient
from src.exceptions.news_sources import NewsSourceError


def document(body: str, *, status: int = 200) -> httpx.Response:
    return httpx.Response(status, text=body, headers={"Content-Type": "text/html; charset=utf-8"})


@asynccontextmanager
async def source_client(
    pages: dict[str, httpx.Response], *, max_response_bytes: int = 10000,
    requests: list[str] | None = None,
) -> AsyncIterator[NewsSourceClient]:
    async def resolver(host: str, port: int) -> list[str]:
        return ["93.184.216.34"]

    def handler(request: httpx.Request) -> httpx.Response:
        if requests is not None:
            requests.append(request.url.path)
        return pages.get(request.url.path, document("", status=404))

    transport = PinnedPublicTransport(httpx.MockTransport(handler), resolver)
    async with httpx.AsyncClient(transport=transport) as http:
        yield NewsSourceClient(SafeNewsHttpClient(
            http, min_interval_seconds=0, max_response_bytes=max_response_bytes,
        ))


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [
    '<article><header><h2>Model release</h2></header><p>A useful summary.</p>'
    '<footer><time datetime="2026-10-08"></time></footer><a href="/post"></a></article>',
    '<main><article><h1>Newsroom</h1><a href="mailto:press@example.org">Press</a>'
    '<a href="/post"><h2>Model release</h2><p>A useful summary.</p></a>'
    '<a href="/another"><h3>Another release</h3></a></article></main>',
    '<article><a href="/image.png">Image</a><a href="/category/research">Research</a>'
    '<span class="item__title"><a href="/post">Model release</a></span>'
    '<p>A useful summary.</p></article>',
    '<div><a href="/post"><div><h3>Model release</h3><p>A useful summary.</p></div></a></div>',
    '<noscript><div><div><div><h4>Model release</h4></div><p>A useful summary.</p></div>'
    '<a href="/post">Learn More</a></div></noscript>',
    '<h3><a href="/post">Model release</a></h3>',
    '<div class="post-card"><a class="post-card__title" href="/post">Model release</a></div>',
])
async def test_discovery_uses_card_titles_and_links_without_main(body: str) -> None:
    async with source_client({"/news": document(body)}) as source:
        result = await source.discover("https://example.org/news")

    assert result.kind == "html"
    assert result.items[0].url == "https://example.org/post"
    assert result.items[0].title == "Model release"
    assert result.warnings


@pytest.mark.asyncio
@pytest.mark.parametrize(("body", "expected_date"), [
    ('<a href="/post" title="Model release"><code>08 Oct 2026</code> · Model release</a>',
     datetime(2026, 10, 8, tzinfo=timezone.utc)),
    ('<a href="/post"><p>Model release</p><span><p>October 8, 2026</p><p>5 min read</p></span></a>',
     datetime(2026, 10, 8, tzinfo=timezone.utc)),
    ('<a href="/post"><div><time>Oct 8, 2026</time><span>Research</span></div>'
     '<span class="PublicationList__title">Model release</span></a>',
     datetime(2026, 10, 8, tzinfo=timezone.utc)),
])
async def test_discovery_retains_dated_list_entries(body: str, expected_date: datetime) -> None:
    async with source_client({"/news": document(body)}) as source:
        result = await source.discover("https://example.org/news")

    assert [(item.title, item.published_at) for item in result.items] == [("Model release", expected_date)]


@pytest.mark.asyncio
async def test_discovery_ignores_navigation_assets_and_document_references() -> None:
    body = '''<header><a href="/menu"><h2>Header</h2></a></header>
      <div role="navigation"><a href="/menu-two"><h3>Menu</h3></a></div>
      <app-header><a href="/tools"><h3>Tools</h3></a></app-header>
      <div class="navbar-dropdown"><a href="/topic"><h3>Topic</h3></a></div>
      <main><a href="/blog">Blog</a><a href="/contact">Contact</a>
        <a href="https://avatar.example.org/"><h2>Assistant product</h2></a>
        <h1><a class="block__title" href="/about">About the site</a></h1>
        <a href="https://other.example/chat"><div class="title-random">Community chat</div></a>
        <a href="#contents"><h2>Contents</h2></a><a href="/news"><h3>News</h3></a>
        <a href="/tag/research"><h3>Research</h3></a><a href="/site/ai"><h3>AI topic</h3></a>
        <a href="/chart.png"><h3>Chart</h3></a><a href="/handbook.pdf"><h3>Download</h3></a>
        <article><h1>API documentation</h1><p>Get a <a href="https://other.example/key">key</a>.</p>
          <h2>Invocation</h2><p>Read the <a href="/reference">reference</a>.</p><h2>Examples</h2>
        </article><div class="entry">Worked at <a href="https://other.example/">A company</a></div>
      </main>'''
    async with source_client({"/news": document(body)}) as source:
        with pytest.raises(NewsSourceError) as error:
            await source.discover("https://example.org/news")

    assert error.value.code == "empty_preview"


@pytest.mark.asyncio
async def test_discovery_preserves_explicit_selectors_and_scope() -> None:
    body = '<div class="entry"><a href="/site/ai">Custom source label</a><span class="date">2026-10-08</span></div>'
    config = {"item_selector": ".entry", "title_selector": "a", "date_selector": ".date"}
    async with source_client({"/news": document(body)}) as source:
        result = await source.discover("https://example.org/news", "html", config)
        scoped = await source.discover("https://example.org/news", "html", {
            "item_selector": ".entry a", "title_selector": ":scope", "link_selector": ":scope",
        })

    assert result.items[0].title == scoped.items[0].title == "Custom source label"
    assert result.items[0].url == "https://example.org/site/ai"
    assert result.items[0].published_at == datetime(2026, 10, 8, tzinfo=timezone.utc)
    assert not result.warnings


@pytest.mark.asyncio
async def test_discovery_normalizes_and_deduplicates_card_links() -> None:
    body = '<article><h2><a href="/post?utm_source=news">Model release</a></h2></article>'
    body += '<a href="/post"><h3>Duplicate release</h3></a>'
    async with source_client({"/news": document(body)}) as source:
        result = await source.discover("https://example.org/news")

    assert [(item.url, item.title) for item in result.items] == [("https://example.org/post", "Model release")]


@pytest.mark.asyncio
@pytest.mark.parametrize("alternate", [
    document("Missing", status=404),
    document('<!DOCTYPE html><html><h1>Temporary landing page</h1></html>'),
    document('<rss version="2.0"><channel><title>Empty feed</title></channel></rss>'),
    document('<!DOCTYPE rss [<!ENTITY x SYSTEM "file:///etc/passwd">]><rss>&x;</rss>'),
    document("x" * 1025),
])
async def test_failed_alternate_preserves_checked_html_preview(alternate: httpx.Response) -> None:
    body = '<link rel="alternate" type="application/rss+xml" href="/feed">'
    body += '<a href="/post"><h2>Model release</h2></a>'
    async with source_client({"/news": document(body), "/feed": alternate}, max_response_bytes=1024) as source:
        result = await source.discover("https://example.org/news")

    assert result.kind == "html"
    assert result.url == "https://example.org/news"
    assert result.items[0].title == "Model release"
    assert any("лента недоступна" in warning for warning in result.warnings)


@pytest.mark.asyncio
async def test_fallback_does_not_fetch_feed_disallowed_by_robots() -> None:
    requests: list[str] = []
    body = '<link rel="alternate" type="application/rss+xml" href="/feed">'
    body += '<a href="/post"><h2>Model release</h2></a>'
    pages = {"/news": document(body), "/robots.txt": document("User-agent: *\nDisallow: /feed\n")}
    async with source_client(pages, requests=requests) as source:
        result = await source.discover("https://example.org/news")

    assert result.kind == "html"
    assert result.items[0].title == "Model release"
    assert requests == ["/robots.txt", "/news"]


@pytest.mark.asyncio
async def test_failed_alternate_without_html_materials_still_fails() -> None:
    body = '<link rel="alternate" type="application/rss+xml" href="/feed"><a href="/about">About</a>'
    async with source_client({"/news": document(body)}) as source:
        with pytest.raises(NewsSourceError) as error:
            await source.discover("https://example.org/news")

    assert error.value.code == "http_status"


@pytest.mark.asyncio
async def test_feed_discovery_prefers_relevant_published_alternate() -> None:
    requests: list[str] = []
    body = '''<!DOCTYPE html><html xmlns="http://www.w3.org/1999/xhtml"><head>
      <link rel="alternate" type="application/rss+xml" href="http://127.0.0.1/private">
      <link rel="alternate" type="application/rss+xml" href="/feed">
      <link rel="alternate" type="application/rss+xml" href="/comments/feed">
      </head><body><a rel="alternate" type="Application/Atom+XML; charset=utf-8" href="/news/feed">Feed</a>
      </body></html>'''
    feed = '''<feed xmlns="http://www.w3.org/2005/Atom"><title>News</title>
      <entry><id>one</id><title>Model release</title><link href="/post"/></entry></feed>'''
    async with source_client({"/news": document(body), "/news/feed": document(feed)}, requests=requests) as source:
        result = await source.discover("https://example.org/news")

    assert result.kind == "rss"
    assert result.url == "https://example.org/news/feed"
    assert result.items[0].title == "Model release"
    assert requests == ["/robots.txt", "/news", "/news/feed"]
