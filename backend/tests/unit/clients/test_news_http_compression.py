"""Bounded content decoding at the real source HTTP client boundary."""

import gzip
import random
import tracemalloc
import zlib
from collections.abc import AsyncIterator

import httpx
import pytest

from src.clients.news_http import PinnedPublicTransport, SafeNewsHttpClient
from src.exceptions.news_sources import NewsRobotsError, NewsSourceError

PUBLIC_IP = "93.184.216.34"
FEED = b'<rss version="2.0"><channel><title>News</title></channel></rss>'


class BodyStream(httpx.AsyncByteStream):
    def __init__(self, body: bytes, chunk_size: int = 7) -> None:
        self.body = body
        self.chunk_size = chunk_size
        self.bytes_read = 0
        self.closed = False

    async def __aiter__(self) -> AsyncIterator[bytes]:
        for start in range(0, len(self.body), self.chunk_size):
            chunk = self.body[start:start + self.chunk_size]
            self.bytes_read += len(chunk)
            yield chunk

    async def aclose(self) -> None:
        self.closed = True


async def public_resolver(host: str, port: int) -> list[str]:
    return [PUBLIC_IP]


def document(body: bytes, encoding: str, **headers: str) -> httpx.Response:
    return httpx.Response(
        200, stream=BodyStream(body),
        headers={"Content-Type": "application/rss+xml", "Content-Encoding": encoding, **headers},
    )


async def fetch(response: httpx.Response, max_bytes: int = 1024) -> bytes:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404) if request.url.path == "/robots.txt" else response

    transport = PinnedPublicTransport(httpx.MockTransport(handler), public_resolver)
    async with httpx.AsyncClient(transport=transport) as http:
        client = SafeNewsHttpClient(http, max_response_bytes=max_bytes, min_interval_seconds=0)
        result = await client.get("https://example.org/feed")
    return result.content


@pytest.mark.parametrize("encoding,wbits", [
    ("gzip", 31), (" GZip ", 31), ("x-gzip", 31),
    ("deflate", 15), ("deflate", -15),
])
async def test_compressed_feed(encoding: str, wbits: int) -> None:
    response = document(zlib.compress(FEED, wbits=wbits), encoding)
    assert await fetch(response) == FEED
    assert response.is_closed


@pytest.mark.parametrize("encoding,wbits", [("gzip", 31), ("deflate", 15), ("deflate", -15)])
async def test_decompression_continues_across_multiple_read_chunks(encoding: str, wbits: int) -> None:
    body = random.Random(0).randbytes(32768)
    compressed = zlib.compress(body, wbits=wbits)
    assert len(compressed) > 16384
    assert await fetch(document(compressed, encoding), max_bytes=65536) == body


@pytest.mark.parametrize("blocked", [False, True])
async def test_compressed_robots_is_enforced_before_feed(blocked: bool) -> None:
    calls: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.path == "/robots.txt":
            robots = b"User-agent: *\nDisallow: " + (b"/feed" if blocked else b"") + b"\n"
            response = document(gzip.compress(robots), "gzip")
            response.headers["Content-Type"] = "text/plain"
            return response
        return document(gzip.compress(FEED), "gzip")

    transport = PinnedPublicTransport(httpx.MockTransport(handler), public_resolver)
    async with httpx.AsyncClient(transport=transport) as http:
        client = SafeNewsHttpClient(http, min_interval_seconds=0)
        if blocked:
            with pytest.raises(NewsRobotsError):
                await client.get("https://example.org/feed")
        else:
            result = await client.get("https://example.org/feed", headers={"accept-encoding": "br, zstd"})
            assert result.content == FEED
    assert [request.url.path for request in calls] == (["/robots.txt"] if blocked else ["/robots.txt", "/feed"])
    assert all(request.url.host == PUBLIC_IP for request in calls)
    assert all(request.headers["Host"] == "example.org" for request in calls)
    assert all(request.headers["Accept-Encoding"] == "gzip, deflate" for request in calls)


@pytest.mark.parametrize("encoding,wbits", [("gzip", 31), ("deflate", 15), ("deflate", -15)])
@pytest.mark.parametrize("size", [1024, 1025])
async def test_expanded_limit_is_exact(encoding: str, wbits: int, size: int) -> None:
    body = b"x" * size
    response = document(zlib.compress(body, wbits=wbits), encoding)
    if size == 1024:
        assert await fetch(response) == body
    else:
        with pytest.raises(NewsSourceError) as error:
            await fetch(response)
        assert error.value.code == "response_too_large"
        assert not error.value.retryable
    assert response.is_closed


@pytest.mark.parametrize("size_header", [None, "1", "200000", "9" * 5000])
async def test_wire_limit_applies_even_to_a_tiny_expanded_body(size_header: str | None) -> None:
    compressed = gzip.compress(b"ok")
    # A valid, large gzip comment increases wire size without expanded data.
    body = compressed[:3] + b"\x10" + compressed[4:10] + b"a" * 20000 + b"\x00" + compressed[10:]
    headers = {} if size_header is None else {"Content-Length": size_header}
    response = document(body, "gzip", **headers)
    stream = response.stream
    with pytest.raises(NewsSourceError) as error:
        await fetch(response)
    assert error.value.code == "response_too_large"
    assert isinstance(stream, BodyStream) and stream.closed
    if size_header in {None, "1"}:
        assert 0 < stream.bytes_read < len(body)
    else:
        assert stream.bytes_read == 0


async def test_compression_bomb_is_rejected_before_large_allocation() -> None:
    response = document(gzip.compress(b"x" * (8 * 1024 * 1024)), "gzip")
    tracemalloc.start()
    try:
        with pytest.raises(NewsSourceError) as error:
            await fetch(response, max_bytes=64 * 1024)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert error.value.code == "response_too_large"
    assert peak < 2 * 1024 * 1024


@pytest.mark.parametrize("encoding,body", [
    ("gzip", b""),
    ("gzip", b"not a gzip stream"),
    ("gzip", gzip.compress(FEED)[:-1]),
    ("gzip", gzip.compress(FEED)[:-8] + b"\x00" * 8),
    ("gzip", gzip.compress(FEED) + b"trailing garbage"),
    ("gzip", gzip.compress(FEED) + gzip.compress(b"second")[:-1]),
    ("deflate", b""),
    ("deflate", b"\x78"),
    ("deflate", zlib.compress(FEED)[:-1]),
    ("deflate", zlib.compress(FEED)[:-4] + b"\x00" * 4),
    ("deflate", zlib.compress(FEED) + b"trailing garbage"),
    ("deflate", zlib.compress(FEED, wbits=-15)[:-1]),
    ("deflate", zlib.compress(FEED, wbits=-15) + b"trailing garbage"),
])
async def test_corrupt_or_incomplete_streams_fail_safely(encoding: str, body: bytes) -> None:
    response = document(body, encoding)
    with pytest.raises(NewsSourceError) as error:
        await fetch(response)
    assert error.value.code == "content_encoding"
    assert not error.value.retryable
    assert response.is_closed


@pytest.mark.parametrize("encoding", ["br", "zstd", "compress", "gzip, deflate", "gzip, gzip", "identity, gzip", ""])
async def test_unsupported_or_layered_codings_are_rejected_without_reading(encoding: str) -> None:
    response = document(b"untrusted body", encoding)
    stream = response.stream
    with pytest.raises(NewsSourceError) as error:
        await fetch(response)
    assert error.value.code == "content_encoding"
    assert isinstance(stream, BodyStream) and stream.bytes_read == 0 and stream.closed


async def test_concatenated_gzip_members_use_one_expanded_limit() -> None:
    body = gzip.compress(b"a" * 512) + gzip.compress(b"b" * 512)
    assert await fetch(document(body, "gzip")) == b"a" * 512 + b"b" * 512
    with pytest.raises(NewsSourceError) as error:
        await fetch(document(body + gzip.compress(b"x"), "gzip"))
    assert error.value.code == "response_too_large"


async def test_gzip_member_can_end_exactly_at_a_read_chunk_boundary() -> None:
    first = gzip.compress(b"first")
    padding = b"a" * (16384 - len(first) - 1)
    first = first[:3] + b"\x10" + first[4:10] + padding + b"\x00" + first[10:]
    assert len(first) == 16384
    body = first + gzip.compress(b"second")
    assert await fetch(document(body, "gzip"), max_bytes=32768) == b"firstsecond"


async def test_gzip_member_limit_bounds_empty_stream_processing() -> None:
    member = gzip.compress(b"")
    assert await fetch(document(member * 32, "gzip")) == b""
    with pytest.raises(NewsSourceError) as error:
        await fetch(document(member * 33, "gzip"))
    assert error.value.code == "content_encoding"


@pytest.mark.parametrize("status", [304, 404])
async def test_bodyless_status_does_not_attempt_decompression(status: int) -> None:
    response = document(b"not a gzip stream", "gzip")
    response.status_code = status
    stream = response.stream
    assert await fetch(response) == b""
    assert isinstance(stream, BodyStream) and stream.bytes_read == 0 and stream.closed
