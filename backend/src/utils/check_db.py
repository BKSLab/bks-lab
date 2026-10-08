"""Database connectivity check used in the application lifespan."""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)


async def check_database(engine: AsyncEngine) -> None:
    """Verify that the database answers a trivial query.

    Args:
        engine: Application async engine.

    Raises:
        Exception: Any driver/connection error is re-raised so the
            application refuses to start in a broken state.
    """
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Database connectivity check failed")
        raise
    logger.info("Database connectivity check passed")
