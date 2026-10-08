"""Application entry point: run with `hypercorn main:app`."""

import logging
import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from src.api import admin, articles, categories, forms, health, news, notes, projects, stats
from src.background_tasks.admin_sessions import cleanup_admin_sessions
from src.core.admin_headers import AdminNoStoreMiddleware
from src.core.limiter import limiter
from src.core.logging import setup_logging
from src.core.settings import get_settings
from src.db.session import async_session_factory, engine
from src.exceptions.admin import ServiceError
from src.exceptions.repositories import RepositoryError
from src.utils.check_db import check_database

setup_logging()
settings = get_settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Verify critical dependencies before serving; dispose them on shutdown."""
    logger.info("Starting %s", settings.app.name)
    await check_database(engine)
    cleanup = asyncio.create_task(cleanup_admin_sessions(
        async_session_factory, settings.admin.cleanup_interval_seconds
    ))
    try:
        yield
    finally:
        cleanup.cancel()
        with suppress(asyncio.CancelledError):
            await cleanup
        await engine.dispose()
        logger.info("Shutdown complete")


app = FastAPI(title=settings.app.name, lifespan=lifespan)
app.state.limiter = limiter
app.add_middleware(AdminNoStoreMiddleware)


@app.exception_handler(ServiceError)
async def service_error_handler(request: Request, exc: ServiceError) -> JSONResponse:
    """Expose only the defined use-case error, never its sensitive cause."""
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Ensure even unexpected admin failures cannot be cached or reveal details."""
    logger.error("Unexpected %s on %s", type(exc).__name__, request.url.path)
    headers = {"Cache-Control": "no-store"} if request.url.path.startswith("/api/admin") else {}
    return JSONResponse(status_code=500, content={"detail": "Internal server error"}, headers=headers)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Return the standard {"detail": ...} error shape for 429 responses."""
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": "Rate limit exceeded"},
    )


@app.exception_handler(RepositoryError)
async def repository_error_handler(request: Request, exc: RepositoryError) -> JSONResponse:
    """Map infrastructure repository failures to a generic 500."""
    logger.error("Repository error on %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


app.include_router(health.router, prefix="/api")
app.include_router(articles.router, prefix="/api/v1")
app.include_router(notes.router, prefix="/api/v1")
app.include_router(categories.router, prefix="/api/v1")
app.include_router(projects.router, prefix="/api/v1")
app.include_router(stats.router, prefix="/api/v1")
app.include_router(forms.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api")
app.include_router(news.router, prefix="/api")
