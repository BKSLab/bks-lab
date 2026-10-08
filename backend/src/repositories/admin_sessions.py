"""Atomic session creation, renewal, revocation and expiry cleanup."""

from datetime import datetime

from sqlalchemy import delete, func, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import AdminSession
from src.exceptions.repositories import AdminSessionRepositoryError


class AdminSessionRepository:
    def __init__(self, db_session: AsyncSession) -> None:
        self.db_session = db_session

    async def create(self, *, token_hash: str, username: str, expires_at: datetime) -> None:
        """Persist only the digest of a cryptographically random bearer token."""
        try:
            self.db_session.add(AdminSession(
                token_hash=token_hash, username=username, expires_at=expires_at
            ))
            await self.db_session.commit()
        except (SQLAlchemyError, OSError) as error:
            await self.db_session.rollback()
            raise AdminSessionRepositoryError("Session creation failed") from error

    async def renew(
        self, *, token_hash: str, username: str, now: datetime, expires_at: datetime
    ) -> bool:
        """Atomically extend a valid session; expired/revoked tokens cannot revive."""
        try:
            result = await self.db_session.execute(
                update(AdminSession)
                .where(
                    AdminSession.token_hash == token_hash,
                    AdminSession.username == username,
                    AdminSession.expires_at > now,
                )
                .values(expires_at=func.greatest(AdminSession.expires_at, expires_at))
                .returning(AdminSession.token_hash)
            )
            found = result.scalar_one_or_none() is not None
            await self.db_session.commit()
            return found
        except (SQLAlchemyError, OSError) as error:
            await self.db_session.rollback()
            raise AdminSessionRepositoryError("Session renewal failed") from error

    async def delete(self, token_hash: str) -> None:
        """Revoke one session without affecting other devices."""
        try:
            await self.db_session.execute(
                delete(AdminSession).where(AdminSession.token_hash == token_hash)
            )
            await self.db_session.commit()
        except (SQLAlchemyError, OSError) as error:
            await self.db_session.rollback()
            raise AdminSessionRepositoryError("Session revocation failed") from error

    async def delete_expired(self, now: datetime) -> None:
        """Remove expired records; an index supports the scheduled cleanup."""
        try:
            await self.db_session.execute(
                delete(AdminSession).where(AdminSession.expires_at <= now)
            )
            await self.db_session.commit()
        except (SQLAlchemyError, OSError) as error:
            await self.db_session.rollback()
            raise AdminSessionRepositoryError("Session cleanup failed") from error
