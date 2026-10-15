"""Bounded diagnostics use real RSS/HTML parsing without fetching external pages."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import httpx
import pytest

from src.clients.news_http import NewsHttpResponse, SafeNewsHttpClient
from src.clients.news_sources import NewsSourceClient
from src.exceptions.news_sources import NewsSourceError
from src.schemas.news_collection import CollectedItem


SUMMARY = "A substantial source description explains the experiment and its measured limitations. " * 10
CUTOFF = datetime(2026, 10, 10, tzinfo=timezone.utc)


def source_client(body: str = "", *, status: int = 200) -> tuple[NewsSourceClient, AsyncMock]:
    http = AsyncMock(spec=SafeNewsHttpClient)
    http.get.return_value = NewsHttpResponse("https://example.org/news", status, body.encode(), httpx.Headers())
    return NewsSourceClient(http), http


def feed(entries: str) -> str:
    return '<rss version="2.0"><channel><title>News</title>' + entries + '</channel></rss>'


def stored_item() -> CollectedItem:
    return CollectedItem(None, "https://example.org/post", "https://example.org/post", "Publication")


@pytest.mark.asyncio
async def test_rss_reports_safe_skip_reasons_without_changing_cutoff_or_deduplication():
    body = feed(f'''<item><title><![CDATA[<b>Old</b><script>hidden()</script>{'x' * 1100}]]></title>
      <link>https://example.org/old?utm_source=feed</link><pubDate>01 Oct 2026 00:00:00 GMT</pubDate></item>
      <item><title>Duplicate</title><link>https://example.org/old</link></item>
      <item><title>Unsafe</title><link>http://127.0.0.1/private</link></item>
      <item><title>Missing link</title></item><item><link>https://example.org/untitled</link></item>
      <item><title>Current</title><link>https://example.org/current</link><description>{SUMMARY}</description></item>''')
    source, http = source_client(body)

    result = await source.fetch(url="https://example.org/news", kind="rss", config={}, cutoff=CUTOFF)

    assert [item.title for item in result.items] == ["Current"]
    assert [(row["reason"], row["stage"]) for row in result.skipped] == [
        ("Дата публикации раньше начала периода сбора.", "filter"),
        ("Повторная ссылка на публикацию.", "filter"),
        ("Некорректная или небезопасная ссылка на публикацию.", "parsing"),
        ("Отсутствует ссылка на публикацию.", "parsing"),
        ("Отсутствует заголовок публикации.", "parsing"),
    ]
    assert [row["url"] for row in result.skipped] == [
        "https://example.org/old", "https://example.org/old", None, None, "https://example.org/untitled",
    ]
    assert len(result.skipped[0]["title"]) == 1000
    assert "<" not in result.skipped[0]["title"] and "hidden" not in result.skipped[0]["title"]
    assert all(row["outcome"] == "skipped" for row in result.skipped)
    assert result.http_status == 200
    assert not result.limit_reached and not result.diagnostics_truncated
    assert http.get.await_count == 1


@pytest.mark.asyncio
async def test_html_reports_explicit_card_failures_and_dated_duplicates():
    body = f'''<div class="entry"><h2>Missing link</h2></div>
      <div class="entry"><h2>Unsafe</h2><a href="http://127.0.0.1/private"></a></div>
      <div class="entry"><h2></h2><a href="/untitled"></a></div>
      <div class="entry"><h2>Old</h2><a href="/old"></a><time datetime="2026-10-01"></time></div>
      <div class="entry"><h2>Duplicate</h2><a href="/old"></a></div>
      <div class="entry"><h2>Current</h2><a href="/current"></a><p>{SUMMARY}</p></div>'''
    source, _ = source_client(body)

    result = await source.fetch(
        url="https://example.org/news", kind="html", config={"item_selector": ".entry"}, cutoff=CUTOFF,
    )

    assert [item.title for item in result.items] == ["Current"]
    assert [row["reason"] for row in result.skipped] == [
        "Отсутствует ссылка на публикацию.",
        "Некорректная или небезопасная ссылка на публикацию.",
        "Отсутствует заголовок публикации.",
        "Дата публикации раньше начала периода сбора.",
        "Повторная ссылка на публикацию.",
    ]
    assert result.skipped[1]["url"] is None


@pytest.mark.asyncio
async def test_automatic_html_reports_non_articles_without_navigation_spam():
    body = f'''<nav><a href="/menu"><h2>Navigation</h2></a></nav>
      <a href="/tag/research"><h2>Research category</h2></a>
      <a href="/chart.png"><h2>Chart</h2></a>
      <a href="/current"><h2>Current</h2><p>{SUMMARY}</p></a>'''
    source, _ = source_client(body)

    result = await source.fetch(url="https://example.org/news", kind="html", config={})

    assert [item.title for item in result.items] == ["Current"]
    assert [(row["title"], row["reason"]) for row in result.skipped] == [
        ("Research category", "Ссылка не ведёт на публикацию."),
        ("Chart", "Ссылка не ведёт на публикацию."),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["rss", "html"])
async def test_reached_limit_does_not_report_unexamined_candidates(kind):
    if kind == "rss":
        body = feed(f'''<item><title>Current</title><link>https://example.org/current</link>
          <description>{SUMMARY}</description></item><item><title>Unexamined</title></item>''')
    else:
        body = f'''<a href="/current"><h2>Current</h2><p>{SUMMARY}</p></a>
          <a href="http://127.0.0.1/private"><h2>Unexamined</h2></a>'''
    source, http = source_client(body)

    result = await source.fetch(url="https://example.org/news", kind=kind, config={}, max_items=1)

    assert len(result.items) == 1 and result.limit_reached
    assert result.skipped == []
    assert not result.diagnostics_truncated
    assert http.get.await_count == 1


@pytest.mark.asyncio
async def test_skip_diagnostics_are_bounded_and_isolated_between_concurrent_fetches():
    source, http = source_client()

    async def get(url, **kwargs):
        count = 205 if url.endswith("/many") else 1
        entries = "".join(f'<item><title>Missing link {index}</title></item>' for index in range(count))
        return NewsHttpResponse(url, 200, feed(entries).encode(), httpx.Headers())

    http.get.side_effect = get
    many, small = await asyncio.gather(*(
        source.fetch(url=f"https://example.org/{path}", kind="rss", config={}) for path in ("many", "small")
    ))

    assert len(many.skipped) == 200 and many.diagnostics_truncated
    assert len(small.skipped) == 1 and not small.diagnostics_truncated
    assert not many.limit_reached and not small.limit_reached
    assert not many.items and not small.items


@pytest.mark.asyncio
async def test_not_modified_retains_http_status_and_empty_diagnostics():
    source, http = source_client(status=304)

    result = await source.fetch(
        url="https://example.org/news", kind="rss", config={}, etag='"stable"', last_modified="yesterday",
    )

    assert result.not_modified and result.http_status == 304
    assert result.etag == '"stable"' and result.last_modified == "yesterday"
    assert not result.items and not result.skipped
    assert not result.limit_reached and not result.diagnostics_truncated
    http.get.assert_awaited_once_with(
        "https://example.org/news", headers={"If-None-Match": '"stable"', "If-Modified-Since": "yesterday"},
    )


@pytest.mark.asyncio
async def test_page_http_failure_reports_fetch_stage_and_safe_status_detail():
    source, _ = source_client(status=403)

    result = await source.refetch([stored_item()])

    metadata = result.items[0].metadata
    assert metadata["collection_status"] == "fetch_failed"
    assert metadata["collection_stage"] == "fetch"
    assert metadata["collection_error_code"] == "http_status"
    assert "HTTP 403" in metadata["collection_warning"]
    assert metadata["collection_warning"].startswith(
        "Не удалось получить текст страницы; сохранена карточка источника."
    )
    assert metadata["collection_warning"] in result.warnings


@pytest.mark.asyncio
@pytest.mark.parametrize(("code", "expected"), [
    ("http_unavailable", "не ответил вовремя"),
    ("robots_denied", "robots.txt"),
    ("dns_timeout", "Истекло время"),
    ("unexpected_failure", "Ошибка получения страницы"),
    ("unsafe/<script>code", "Ошибка получения страницы"),
])
async def test_page_error_details_do_not_retain_external_messages_or_unsafe_codes(code, expected):
    source, http = source_client()
    http.get.side_effect = NewsSourceError(code, "SECRET https://user:pass@example.org/request?key=SECRET")

    result = await source.refetch([stored_item()])

    metadata = result.items[0].metadata
    assert metadata["collection_stage"] == "fetch"
    assert expected in metadata["collection_warning"]
    assert "SECRET" not in metadata["collection_warning"] and "https://" not in metadata["collection_warning"]
    if code.startswith("unsafe/"):
        assert "collection_error_code" not in metadata
    else:
        assert metadata["collection_error_code"] == code


@pytest.mark.asyncio
async def test_insufficient_text_records_extraction_stage_and_recovery_clears_old_details():
    source, http = source_client("<main><p>Short text</p></main>")
    first = await source.refetch([stored_item()])
    metadata = first.items[0].metadata
    assert metadata["collection_status"] == "insufficient_text"
    assert metadata["collection_stage"] == "extraction"
    assert "collection_error_code" not in metadata

    metadata["collection_error_code"] = "old_error"
    http.get.return_value = NewsHttpResponse(
        "https://example.org/post", 200, f"<main><p>{SUMMARY}</p></main>".encode(), httpx.Headers(),
    )
    recovered = (await source.refetch(first.items)).items[0].metadata

    assert recovered["collection_status"] == "ready"
    assert "collection_warning" not in recovered
    assert "collection_stage" not in recovered
    assert "collection_error_code" not in recovered
