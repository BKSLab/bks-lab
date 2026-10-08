"""Resource factories shared by the dedicated news worker and isolated tests."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx

from src.clients.llm import LlmClient
from src.clients.news_http import PinnedPublicTransport, SafeNewsHttpClient, resolve_public_host
from src.clients.news_sources import NewsSourceClient
from src.core.news_settings import NewsSettings
from src.services.news_analysis import NewsAnalysisService


@asynccontextmanager
async def news_source_client(settings: NewsSettings) -> AsyncIterator[NewsSourceClient]:
    """Own a bounded public-web pool with DNS pinning, no proxy and no cookies."""
    logging.getLogger("httpx").setLevel(logging.WARNING)
    inner = httpx.AsyncHTTPTransport(
        limits=httpx.Limits(max_connections=settings.http_concurrency, max_keepalive_connections=0),
        retries=0,
    )
    transport = PinnedPublicTransport(inner, resolve_public_host)
    async with httpx.AsyncClient(transport=transport, trust_env=False, follow_redirects=False) as client:
        safe = SafeNewsHttpClient(
            client, concurrency=settings.http_concurrency,
            timeout_seconds=settings.http_timeout_seconds,
            max_response_bytes=settings.http_max_response_bytes,
            max_redirects=settings.http_max_redirects, retries=settings.http_retries,
            min_interval_seconds=settings.source_min_interval_seconds,
        )
        yield NewsSourceClient(safe, settings.max_excerpt_chars)


@asynccontextmanager
async def news_analysis_service(settings: NewsSettings) -> AsyncIterator[NewsAnalysisService | None]:
    """Keep missing credentials a pending state; never create a fake result."""
    if not settings.llm_configured:
        yield None
        return
    logging.getLogger("httpx").setLevel(logging.WARNING)
    async with httpx.AsyncClient(
        trust_env=False, follow_redirects=False,
        timeout=settings.llm_timeout_seconds,
        limits=httpx.Limits(max_connections=settings.llm_concurrency, max_keepalive_connections=settings.llm_concurrency),
    ) as http:
        client = LlmClient(
            http, model=settings.llm_model, url=settings.llm_api_url,
            headers={"Authorization": f"Bearer {settings.llm_api_key.get_secret_value()}",
                     "Content-Type": "application/json"},
            timeout=settings.llm_timeout_seconds, retries=settings.llm_retries,
            temperature=0.2,
        )
        yield NewsAnalysisService(client, settings.llm_model,
                                  settings.max_excerpt_chars, settings.llm_max_tokens)
