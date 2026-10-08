"""Stats use-cases: page view filtering, normalization, hashing, storage."""

import hashlib
import hmac
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlsplit

from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio.session import AsyncSession

from src.exceptions.repositories import StatsRepositoryError
from src.repositories.stats import StatsRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PageViewData:
    """A page view that passed all filters and is ready to be stored."""

    path: str
    note_slug: str | None
    referrer_domain: str | None
    visitor_hash: str


class StatsService:
    """Use-cases for visit statistics."""

    # Generic markers cover whole bot families (googlebot, yandexbot,
    # ahrefsbot, headless chrome, http libraries, uptime monitors).
    BOT_USER_AGENT_MARKERS = (
        "bot",
        "spider",
        "crawl",
        "slurp",
        "headless",
        "curl",
        "wget",
        "python-requests",
        "httpx",
        "monitor",
    )

    ALLOWED_EXACT_PATHS = frozenset(
        {"/", "/blog", "/notes", "/projects", "/about", "/contacts", "/privacy"}
    )
    _SLUG_PATH_PATTERN = re.compile(
        r"^/(?:blog|projects)/[a-z0-9]+(?:-[a-z0-9]+)*$"
    )
    _POST_PATH_PATTERN = re.compile(r"^/blog/post/[a-z0-9]+(?:-[a-z0-9]+)*$")
    _PAGE_PATH_PATTERN = re.compile(
        r"^/(?:blog(?:/[a-z0-9]+(?:-[a-z0-9]+)*)?|notes)/page/\d+$"
    )
    _NOTE_ANCHOR_PATTERN = re.compile(r"^note-([a-z0-9]+(?:-[a-z0-9]+)*)$")

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        stats_secret: str,
        utc_now: Callable[[], datetime],
        referrer_domain_max_length: int,
    ):
        self._session_factory = session_factory
        self._stats_secret = stats_secret
        self._utc_now = utc_now
        self._referrer_domain_max_length = referrer_domain_max_length

    def prepare_page_view(
        self,
        *,
        path: str,
        referrer: str | None,
        ip: str,
        user_agent: str,
    ) -> PageViewData | None:
        """Filter and normalize a page view request.

        Args:
            path: Raw path from the client (may contain query and anchor).
            referrer: Optional referrer URL; only the domain is kept.
            ip: Client IP from forwarded headers (never stored).
            user_agent: Client User-Agent (never stored).

        Returns:
            PageViewData ready to store, or None when the request must be
            silently skipped (bot, path outside the whitelist).
        """
        if self._is_bot(user_agent):
            return None
        clean_path, note_slug = self._normalize_path(path)
        if clean_path is None:
            return None
        return PageViewData(
            path=clean_path,
            note_slug=note_slug,
            referrer_domain=self._extract_referrer_domain(referrer),
            visitor_hash=self._visitor_hash(ip=ip, user_agent=user_agent),
        )

    async def save_page_view(self, view: PageViewData) -> None:
        """Persist a prepared page view (runs as a background task)."""
        try:
            async with self._session_factory() as session:
                repository = StatsRepository(session)
                await repository.save_page_view(
                    path=view.path,
                    note_slug=view.note_slug,
                    referrer_domain=view.referrer_domain,
                    visitor_hash=view.visitor_hash,
                )
        except StatsRepositoryError as error:
            # Background task: the 202 was already sent; log and move on.
            logger.error("Failed to store page view %s: %s", view.path, error)

    # Filtering and normalization

    def _is_bot(self, user_agent: str) -> bool:
        lowered = user_agent.lower()
        return any(marker in lowered for marker in self.BOT_USER_AGENT_MARKERS)

    def _normalize_path(self, raw_path: str) -> tuple[str | None, str | None]:
        """Strip query/anchor, extract the note anchor, apply the whitelist.

        Returns:
            (path, note_slug) when the path is whitelisted, (None, None)
            otherwise. note_slug is extracted on the notes feed and its pages.
        """
        path, _, fragment = raw_path.partition("#")
        path = path.partition("?")[0]
        if not self._is_allowed_path(path):
            return None, None
        note_slug = None
        if (path == "/notes" or path.startswith("/notes/page/")) and fragment:
            match = self._NOTE_ANCHOR_PATTERN.fullmatch(fragment)
            # Keep the page view even when its anchor exceeds the DB column.
            if match and len(match.group(1)) <= 200:
                note_slug = match.group(1)
        return path, note_slug

    def _is_allowed_path(self, path: str) -> bool:
        return (
            path in self.ALLOWED_EXACT_PATHS
            or bool(self._SLUG_PATH_PATTERN.match(path))
            or bool(self._POST_PATH_PATTERN.match(path))
            or bool(self._PAGE_PATH_PATTERN.match(path))
        )

    def _extract_referrer_domain(self, referrer: str | None) -> str | None:
        """Keep only the referrer domain; invalid values become None."""
        if not referrer:
            return None
        try:
            parsed = urlsplit(referrer)
        except ValueError:
            return None
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            return None
        return parsed.hostname.lower()[: self._referrer_domain_max_length]

    # Hashing

    def _daily_salt(self) -> str:
        """Derive the salt of the day from the master secret and UTC date."""
        day = self._utc_now().date().isoformat()
        return hmac.new(
            self._stats_secret.encode("utf-8"), day.encode("utf-8"), hashlib.sha256
        ).hexdigest()

    def _visitor_hash(self, *, ip: str, user_agent: str) -> str:
        """Hash the visitor identity; IP and User-Agent are never stored."""
        raw = f"{self._daily_salt()}{ip}{user_agent}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
