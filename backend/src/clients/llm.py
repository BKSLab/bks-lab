"""Chat Completions client adapted from vera_rag_service/LLM_CLIENT_REFERENCE.md.

The reference request/extraction/retry interface is retained. Logging excludes
provider bodies and validation input; permanent 4xx errors fail immediately.
"""

import asyncio
import functools
import logging
import random
from collections.abc import Callable
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from src.exceptions.llm import LlmApiRequestError, LlmClientContentError, LlmClientRequestError

logger = logging.getLogger(__name__)
PydanticModel = TypeVar("PydanticModel", bound=BaseModel)


class LlmClient:
    """Reusable HTTPX client for OpenAI-compatible Chat Completions APIs."""

    DEFAULT_TIMEOUT_SECONDS = 90
    DEFAULT_RETRIES = 3
    DEFAULT_RETRY_DELAY = 1.0
    DEFAULT_MAX_RETRY_DELAY = 30.0
    JITTER_RATIO = 0.1

    def __init__(
        self, httpx_client: httpx.AsyncClient, model: str, url: str,
        headers: dict[str, str], temperature: float | None = None,
        stream: bool = False, timeout: float = DEFAULT_TIMEOUT_SECONDS,
        retries: int = DEFAULT_RETRIES, delay: float = DEFAULT_RETRY_DELAY,
        max_delay: float = DEFAULT_MAX_RETRY_DELAY, extra_payload: dict | None = None,
    ) -> None:
        self.httpx_client = httpx_client
        self.model = model
        self.url = url
        self.headers = headers
        self.temperature = temperature
        self.stream = stream
        self.timeout = timeout
        self.retries = retries
        self.delay = delay
        self.max_delay = max_delay
        self.extra_payload = extra_payload or {}

    def _get_backoff_delay(self, attempt: int) -> float:
        base = min(self.max_delay, self.delay * (2 ** (attempt - 1)))
        return base + base * self.JITTER_RATIO * random.random()

    async def _send_request_to_llm(self, payload: dict) -> dict:
        try:
            response = await self.httpx_client.post(
                self.url, headers=self.headers, json=payload, timeout=self.timeout,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            code = error.response.status_code
            raise LlmClientRequestError(
                f"HTTP {code}", retryable=code == 429 or code >= 500,
            ) from None
        except httpx.RequestError as error:
            raise LlmClientRequestError(type(error).__name__) from None
        try:
            data = response.json()
        except ValueError:
            raise LlmClientContentError("Invalid JSON response envelope") from None
        if not isinstance(data, dict):
            raise LlmClientContentError("Invalid response envelope")
        return data

    def _extract_content(self, response: dict) -> str:
        try:
            content = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise LlmClientContentError("Missing message content") from None
        if not isinstance(content, str) or not content.strip():
            raise LlmClientContentError("Empty message content")
        return content

    def _extract_validated(self, response: dict, schema: type[PydanticModel]) -> PydanticModel:
        content = self._extract_content(response)
        try:
            return schema.model_validate_json(content)
        except ValidationError:
            raise LlmClientContentError("Response failed schema validation") from None

    async def _fetch_with_retries(self, payload: dict, extractor: Callable[[dict], Any]) -> Any:
        last_error: Exception | None = None
        for attempt in range(1, self.retries + 1):
            try:
                return extractor(await self._send_request_to_llm(payload))
            except LlmClientContentError as error:
                last_error = error
                logger.warning("LLM content validation failed attempt=%s/%s", attempt, self.retries)
            except LlmClientRequestError as error:
                last_error = error
                logger.warning("LLM request failed attempt=%s/%s reason=%s", attempt, self.retries, error)
                if not error.retryable:
                    raise LlmApiRequestError(str(error), retryable=False) from None
            if attempt < self.retries:
                await asyncio.sleep(self._get_backoff_delay(attempt))
        raise LlmApiRequestError(str(last_error)) from None

    async def get_llm_response(
        self, content: str, prompt: str, model: str | None = None,
        schema: type[PydanticModel] | None = None, max_completion_tokens: int = 6000,
    ) -> str | PydanticModel:
        """Return text or a validated model using the reference client interface."""
        payload: dict[str, Any] = {
            "model": model or self.model,
            "messages": [{"role": "system", "content": prompt}, {"role": "user", "content": content}],
            "max_completion_tokens": max_completion_tokens,
            "stream": self.stream,
        }
        if self.temperature is not None:
            payload["temperature"] = self.temperature
        if schema:
            payload["response_format"] = {"type": "json_object"}
        payload.update(self.extra_payload)
        extractor = functools.partial(self._extract_validated, schema=schema) if schema else self._extract_content
        return await self._fetch_with_retries(payload, extractor)
