"""Scheduled, idempotent removal of expired session digests."""

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.exceptions.repositories import AdminSessionRepositoryError
from src.repositories.admin_sessions import AdminSessionRepository

logger = logging.getLogger(__name__)


async def cleanup_admin_sessions(
    session_factory: async_sessionmaker[AsyncSession], interval_seconds: int,
) -> None:
    """Run until cancelled; concurrent deletes are harmless if workers overlap."""
    while True:
        try:
            async with session_factory() as session:
                await AdminSessionRepository(session).delete_expired(datetime.now(timezone.utc))
        except AdminSessionRepositoryError:
            logger.error("Admin session cleanup failed; will retry next interval")
        await asyncio.sleep(interval_seconds)
