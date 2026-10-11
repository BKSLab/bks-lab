"""Distinguish an inaccessible robots policy from an explicit crawl prohibition."""

import httpx
import pytest

from src.clients.news_http import SafeNewsHttpClient
from src.exceptions.news_sources import NewsSourceError


@pytest.mark.asyncio
@pytest.mark.parametrize("status,body,code", [
    (401, "", "robots_unavailable"),
    (403, "", "robots_unavailable"),
    (200, "User-agent: *\nDisallow: /", "robots_denied"),
])
async def test_unavailable_and_disallowed_robots_stop_before_source(
    status: int, body: str, code: str,
) -> None:
    paths = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        return httpx.Response(status, text=body, headers={"Content-Type": "text/plain"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(NewsSourceError) as error:
            await SafeNewsHttpClient(client, min_interval_seconds=0).get("https://example.org/news")
    assert error.value.code == code
    assert paths == ["/robots.txt"]
    if status != 200:
        assert str(status) in str(error.value)
