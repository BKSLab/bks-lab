"""Single-admin authentication and opaque server-side session lifecycle."""

import hashlib
import re
import secrets
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from src.core.settings import AdminSettings
from src.exceptions.admin import InvalidCredentialsError, NotAuthenticatedError
from src.repositories.admin_sessions import AdminSessionRepository


@dataclass(frozen=True)
class SessionGrant:
    token: str = field(repr=False)
    username: str


class AdminAuthService:
    def __init__(
        self, *, repository: AdminSessionRepository, settings: AdminSettings,
        utc_now: Callable[[], datetime],
    ) -> None:
        self.repository = repository
        self.settings = settings
        self.utc_now = utc_now

    def _configured(self) -> bool:
        return bool(self.settings.username and self.settings.password.get_secret_value())

    @staticmethod
    def _hash(token: str) -> str:
        return hashlib.sha256(token.encode("ascii")).hexdigest()

    async def login(self, username: str, password: str, old_token: str | None) -> SessionGrant:
        """Validate both credentials in constant time and replace a browser's session.

        Raises:
            InvalidCredentialsError: Incorrect or unconfigured credentials.
            AdminSessionRepositoryError: Session storage is unavailable.
        """
        username_matches = secrets.compare_digest(
            username.encode("utf-8"), self.settings.username.encode("utf-8")
        )
        password_matches = secrets.compare_digest(
            password.encode("utf-8"), self.settings.password.get_secret_value().encode("utf-8")
        )
        if not self._configured() or not (username_matches and password_matches):
            raise InvalidCredentialsError
        if old_token and re.fullmatch(r"[A-Za-z0-9_-]{43}", old_token):
            await self.repository.delete(self._hash(old_token))
        token = secrets.token_urlsafe(32)
        await self.repository.create(
            token_hash=self._hash(token), username=self.settings.username,
            expires_at=self.utc_now() + timedelta(seconds=self.settings.session_ttl_seconds),
        )
        return SessionGrant(token=token, username=self.settings.username)

    async def authenticate(self, token: str | None) -> SessionGrant:
        """Reject unknown/expired sessions and slide valid sessions by twelve hours."""
        if not self._configured() or not token or not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
            raise NotAuthenticatedError
        now = self.utc_now()
        valid = await self.repository.renew(
            token_hash=self._hash(token), username=self.settings.username,
            now=now, expires_at=now + timedelta(seconds=self.settings.session_ttl_seconds),
        )
        if not valid:
            raise NotAuthenticatedError
        return SessionGrant(token=token, username=self.settings.username)

    async def logout(self, grant: SessionGrant) -> None:
        """Revoke the authenticated session before clearing its browser cookie."""
        await self.repository.delete(self._hash(grant.token))
