"""API tests for /api/health (real SELECT 1, 503 on database failure)."""

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from main import app
from src.dependencies.db_session import get_db_session


async def test_health_returns_ok_with_working_database(client: AsyncClient) -> None:
    # The `client` fixture overrides get_db_session with the test database.
    response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_health_returns_503_when_database_is_down() -> None:
    broken_engine = create_async_engine("postgresql+asyncpg://u:p@127.0.0.1:1/none")
    broken_factory = async_sessionmaker(broken_engine)

    async def broken_session():
        async with broken_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = broken_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as test_client:
            response = await test_client.get("/api/health")
    finally:
        app.dependency_overrides.clear()
        await broken_engine.dispose()

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
