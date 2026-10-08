"""Bounded public-web requests with DNS pinning and robots policy."""

import asyncio
import ipaddress
import socket
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

import httpx

from src.exceptions.news_sources import NewsRobotsError, NewsSourceError, UnsafeNewsUrlError

USER_AGENT = "BKS-Lab-News/1.0 (+https://bks-lab.ru)"
ROBOT_AGENT = "BKS-Lab-News"
ALLOWED_TYPES = frozenset({
    "application/rss+xml", "application/atom+xml", "application/rdf+xml",
    "application/xml", "text/xml", "text/html", "application/xhtml+xml", "text/plain",
})
Resolver = Callable[[str, int], Awaitable[list[str]]]


def validate_public_url(value: str) -> httpx.URL:
    """Reject credentials, unusual ports and local hostnames before any I/O."""
    try:
        if not isinstance(value, str) or len(value) > 2048 or any(ord(c) < 32 for c in value):
            raise ValueError
        url = httpx.URL(value)
        host = url.host.rstrip(".").lower()
        if (
            url.scheme not in {"http", "https"} or not host or url.userinfo
            or url.port not in {None, 80, 443} or "%" in host or "\\" in value
            or host == "localhost" or host.endswith((".localhost", ".local", ".internal"))
        ):
            raise ValueError
        try:
            _check_address(host)
        except ValueError:
            if "." not in host or ":" in host:
                raise UnsafeNewsUrlError() from None
        return url.copy_with(host=host, fragment=None)
    except (ValueError, httpx.InvalidURL):
        raise UnsafeNewsUrlError() from None


def _check_address(value: str) -> str:
    address = ipaddress.ip_address(value)
    if not address.is_global or address.is_multicast or address.is_reserved:
        raise UnsafeNewsUrlError()
    if isinstance(address, ipaddress.IPv6Address):
        if (
            address.ipv4_mapped or address.sixtofour or address.teredo
            or address in ipaddress.ip_network("64:ff9b::/96")
            or address in ipaddress.ip_network("64:ff9b:1::/48")
        ):
            raise UnsafeNewsUrlError()
    return str(address)


async def resolve_public_host(host: str, port: int) -> list[str]:
    """Validate every DNS answer, including mixed public/private answers."""
    try:
        return [_check_address(host)]
    except ValueError:
        pass
    try:
        answers = await asyncio.get_running_loop().getaddrinfo(
            host, port, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM,
        )
    except OSError:
        raise NewsSourceError("dns_error", "Не удалось определить адрес источника.", retryable=True) from None
    addresses = list(dict.fromkeys(_check_address(answer[4][0]) for answer in answers))
    if not addresses:
        raise NewsSourceError("dns_error", "Источник не имеет доступного адреса.", retryable=True)
    return addresses


class PinnedPublicTransport(httpx.AsyncBaseTransport):
    """Connect only to validated addresses while preserving TLS hostname checks.

    The inner transport must disable keepalive: IP-based pooling must never
    reuse a TLS connection for a different hostname on the same CDN address.
    """

    def __init__(self, inner: httpx.AsyncBaseTransport, resolver: Resolver) -> None:
        self.inner = inner
        self.resolver = resolver

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        url = validate_public_url(str(request.url))
        if request.method != "GET":
            raise UnsafeNewsUrlError()
        timeout = request.extensions.get("timeout", {}).get("connect", 20.0)
        try:
            async with asyncio.timeout(timeout):
                addresses = await self.resolver(url.host, url.port or (443 if url.scheme == "https" else 80))
        except TimeoutError:
            raise NewsSourceError("dns_timeout", "Истекло время проверки адреса.", retryable=True) from None
        if not addresses:
            raise UnsafeNewsUrlError()
        for address in addresses:
            _check_address(address)
        headers = request.headers.copy()
        for name in ("Cookie", "Authorization", "Proxy-Authorization"):
            headers.pop(name, None)
        headers["Host"] = url.netloc.decode("ascii")
        headers["Connection"] = "close"
        extensions = {**request.extensions, "sni_hostname": url.host}
        for index, address in enumerate(addresses[:8]):
            pinned = httpx.Request(
                "GET", url.copy_with(host=address), headers=headers,
                extensions=extensions,
            )
            try:
                return await self.inner.handle_async_request(pinned)
            except (httpx.ConnectError, httpx.ConnectTimeout):
                if index == len(addresses[:8]) - 1:
                    raise
        raise UnsafeNewsUrlError()

    async def aclose(self) -> None:
        await self.inner.aclose()


@dataclass(frozen=True)
class NewsHttpResponse:
    url: str
    status_code: int
    content: bytes
    headers: httpx.Headers


class SafeNewsHttpClient:
    """Source-only HTTP client; injected AsyncClient uses PinnedPublicTransport."""

    def __init__(
        self, client: httpx.AsyncClient, *, concurrency: int = 5,
        timeout_seconds: float = 20, max_response_bytes: int = 2 * 1024 * 1024,
        max_redirects: int = 5, retries: int = 2, min_interval_seconds: float = 1,
    ) -> None:
        self.client = client
        self.semaphore = asyncio.Semaphore(concurrency)
        self.timeout_seconds = timeout_seconds
        self.max_response_bytes = max_response_bytes
        self.max_redirects = max_redirects
        self.retries = retries
        self.min_interval_seconds = min_interval_seconds
        self._robots: dict[str, tuple[float, RobotFileParser]] = {}
        self._robots_locks: dict[str, asyncio.Lock] = {}
        self._rate_locks: dict[str, asyncio.Lock] = {}
        self._last_request: dict[str, float] = {}
        self._crawl_delays: dict[str, float] = {}

    @staticmethod
    def _origin(url: httpx.URL) -> str:
        return f"{url.scheme}://{url.netloc.decode('ascii')}"

    async def get(self, url: str, *, headers: dict[str, str] | None = None) -> NewsHttpResponse:
        """Get a public document; every redirect has its own DNS/robots check."""
        return await self._request(url, headers=headers or {}, robots=True)

    async def _request(
        self, url: str, *, headers: dict[str, str], robots: bool,
    ) -> NewsHttpResponse:
        current = str(validate_public_url(url))
        for redirect in range(self.max_redirects + 1):
            parsed = validate_public_url(current)
            if robots:
                await self._check_robots(parsed)
            result = await self._request_with_retries(parsed, headers)
            if result.status_code not in {301, 302, 303, 307, 308}:
                return result
            if redirect == self.max_redirects or "location" not in result.headers:
                raise NewsSourceError("redirect_limit", "Слишком много перенаправлений источника.")
            next_url = str(validate_public_url(urljoin(current, result.headers["location"])))
            if self._origin(httpx.URL(next_url)) != self._origin(parsed):
                headers = {}
            current = next_url
        raise NewsSourceError("redirect_limit", "Слишком много перенаправлений.")

    async def _request_with_retries(self, url: httpx.URL, headers: dict[str, str]) -> NewsHttpResponse:
        for attempt in range(self.retries):
            try:
                result = await self._request_once(url, headers)
            except (httpx.HTTPError, TimeoutError):
                if attempt + 1 == self.retries:
                    raise NewsSourceError("http_unavailable", "Источник не ответил вовремя.", retryable=True) from None
            else:
                if result.status_code != 429 and result.status_code < 500:
                    return result
                if attempt + 1 == self.retries:
                    raise NewsSourceError("http_unavailable", f"Источник временно недоступен (HTTP {result.status_code}).", retryable=True)
            await asyncio.sleep(min(2 ** attempt, 5))
        raise NewsSourceError("http_unavailable", "Источник недоступен.", retryable=True)

    async def _request_once(self, url: httpx.URL, headers: dict[str, str]) -> NewsHttpResponse:
        origin = self._origin(url)
        lock = self._rate_locks.setdefault(origin, asyncio.Lock())
        async with self.semaphore, lock:
            interval = max(self.min_interval_seconds, self._crawl_delays.get(origin, 0))
            wait = interval - (time.monotonic() - self._last_request.get(origin, 0))
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request[origin] = time.monotonic()
            # Refuse compression to bound memory even for a malicious compressed body.
            request_headers = {"User-Agent": USER_AGENT, "Accept-Encoding": "identity", **headers}
            async with asyncio.timeout(self.timeout_seconds):
                async with self.client.stream(
                    "GET", str(url), headers=request_headers,
                    timeout=self.timeout_seconds, follow_redirects=False,
                ) as response:
                    if response.status_code in {301, 302, 303, 307, 308, 304} or response.status_code >= 400:
                        return NewsHttpResponse(str(url), response.status_code, b"", response.headers)
                    content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                    if content_type not in ALLOWED_TYPES:
                        raise NewsSourceError("content_type", "Источник вернул неподдерживаемый тип документа.")
                    if response.headers.get("content-encoding", "identity").lower() != "identity":
                        raise NewsSourceError("content_encoding", "Источник не поддерживает получение без сжатия.")
                    size_header = response.headers.get("content-length", "")
                    if size_header.isdigit() and int(size_header) > self.max_response_bytes:
                        raise NewsSourceError("response_too_large", "Документ превышает допустимый размер.")
                    parts: list[bytes] = []
                    total = 0
                    async for part in response.aiter_bytes(chunk_size=16384):
                        total += len(part)
                        if total > self.max_response_bytes:
                            raise NewsSourceError("response_too_large", "Документ превышает допустимый размер.")
                        parts.append(part)
                    return NewsHttpResponse(str(url), response.status_code, b"".join(parts), response.headers)

    async def _check_robots(self, url: httpx.URL) -> None:
        origin = self._origin(url)
        lock = self._robots_locks.setdefault(origin, asyncio.Lock())
        async with lock:
            cached = self._robots.get(origin)
            if cached is None or time.monotonic() - cached[0] > 3600:
                result = await self._request(origin + "/robots.txt", headers={}, robots=False)
                parser = RobotFileParser()
                if result.status_code in {404, 410}:
                    parser.parse(["User-agent: *", "Disallow:"])
                elif result.status_code == 200:
                    parser.parse(result.content.decode("utf-8", errors="replace").splitlines())
                else:
                    raise NewsRobotsError()
                delay = parser.crawl_delay(ROBOT_AGENT) or 0
                rate = parser.request_rate(ROBOT_AGENT)
                if rate and rate.requests:
                    delay = max(delay, rate.seconds / rate.requests)
                if delay > 60:
                    raise NewsRobotsError()
                self._crawl_delays[origin] = float(delay)
                self._robots[origin] = (time.monotonic(), parser)
            else:
                parser = cached[1]
        if not parser.can_fetch(ROBOT_AGENT, str(url)):
            raise NewsRobotsError()
