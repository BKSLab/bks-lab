"""Health check endpoint: verifies the database with a real query."""

import logging

from fastapi import APIRouter, Response, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from src.dependencies.db_session import DbSessionDep

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get(
    path="/health",
    summary="Health check",
    description="Runs SELECT 1 against PostgreSQL. Used by docker-compose and nginx healthchecks.",
    operation_id="getHealth",
    responses={
        200: {"description": "Application and database are healthy."},
        503: {"description": "Database is unavailable."},
    },
)
async def health(session: DbSessionDep, response: Response) -> dict[str, str]:
    """Check application health including database connectivity.

    Args:
        session: Request-scoped database session.
        response: Response object for the status code override.

    Returns:
        {"status": "ok"} or 503 {"status": "unavailable"} when the
        database does not answer.
    """
    try:
        await session.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError) as error:
        logger.error("Health check failed: database unavailable: %s", error)
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unavailable"}
    return {"status": "ok"}
