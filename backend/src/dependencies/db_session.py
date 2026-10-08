"""Level 0 dependency: the per-request database session."""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import async_session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a request-scoped async session."""
    async with async_session_factory() as session:
        yield session


DbSessionDep = Annotated[AsyncSession, Depends(get_db_session)]
