"""Async engine and session factory (module-level, configured from settings)."""

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.core.settings import get_settings

settings = get_settings()

engine = create_async_engine(url=settings.db.database_url, pool_size=5, max_overflow=5)

async_session_factory = async_sessionmaker(engine, expire_on_commit=False)
