"""Frontend cache revalidation webhook client.

After a successful content mutation the backend pings the Next.js
revalidate route so cached pages are refreshed immediately. The webhook is
best-effort: when it is unconfigured or unreachable the mutation still
succeeds — the frontend cache expires on its own (`revalidate = 300`).
The secret is never logged and never included in API responses.
"""

import logging

import httpx

from src.core.settings import RevalidateSettings

logger = logging.getLogger(__name__)


class RevalidationClient:
    """Best-effort caller of POST {FRONTEND_INTERNAL_URL}/api/revalidate."""

    def __init__(
        self,
        settings: RevalidateSettings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout_seconds: float = 5.0,
    ) -> None:
        self.settings = settings
        self.transport = transport
        self.timeout_seconds = timeout_seconds

    async def revalidate_content(self) -> None:
        """Ping the frontend webhook; no-op when unconfigured, never raises."""
        if not self.settings.configured:
            if self.settings.frontend_internal_url or (
                self.settings.secret and self.settings.secret.get_secret_value()
            ):
                logger.warning(
                    "Revalidation is half-configured (URL or secret missing); skipping webhook"
                )
            return
        url = f"{self.settings.frontend_internal_url}/api/revalidate"
        secret = self.settings.secret
        assert secret is not None  # guaranteed by settings.configured
        try:
            async with httpx.AsyncClient(
                transport=self.transport, trust_env=False, timeout=self.timeout_seconds
            ) as client:
                response = await client.post(
                    url,
                    headers={"Authorization": f"Bearer {secret.get_secret_value()}"},
                )
        except (httpx.HTTPError, OSError) as error:
            logger.warning("Revalidate webhook failed: %s", type(error).__name__)
            return
        if response.status_code >= 400:
            logger.warning("Revalidate webhook answered HTTP %s", response.status_code)
