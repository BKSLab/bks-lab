"""Run the real migration chain and check metadata against an isolated database."""

import asyncio
import os
import sys
from pathlib import Path

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine


async def test_migrations_upgrade_check_downgrade_and_reupgrade(postgres_url):
    admin_engine = create_async_engine(postgres_url, isolation_level="AUTOCOMMIT")
    async with admin_engine.connect() as connection:
        await connection.execute(text("CREATE DATABASE migration_check"))
    await admin_engine.dispose()
    parsed = make_url(postgres_url)
    environment = {
        **os.environ,
        "POSTGRES_HOST": parsed.host,
        "POSTGRES_PORT": str(parsed.port),
        "POSTGRES_USER": parsed.username,
        "POSTGRES_PASSWORD": parsed.password,
        "POSTGRES_DB": "migration_check",
    }

    async def alembic(*args):
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "alembic", *args,
            cwd=Path(__file__).resolve().parents[2], env=environment,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
        assert process.returncode == 0, (stdout + stderr).decode(errors="replace").replace(parsed.password, "***")

    await alembic("upgrade", "head")
    await alembic("check")
    await alembic("downgrade", "0001")
    engine = create_async_engine(parsed.set(database="migration_check"))
    async with engine.connect() as connection:
        names = await connection.run_sync(lambda conn: inspect(conn).get_table_names())
        assert "content_items" in names and "page_views" in names
        assert "admin_sessions" not in names and "subscribers" not in names
    await engine.dispose()
    await alembic("upgrade", "head")
    await alembic("check")


@pytest.mark.parametrize(
    "password", ["test@fixture", "test%fixture", "test%2F@fixture"],
    ids=["at-sign", "percent", "percent-like-escape"],
)
async def test_actual_alembic_environment_accepts_special_credentials_offline(password):
    environment = {
        **os.environ,
        "POSTGRES_HOST": "db",
        "POSTGRES_PORT": "5432",
        "POSTGRES_USER": "test@user",
        "POSTGRES_PASSWORD": password,
        "POSTGRES_DB": "bks_test",
    }
    process = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "alembic", "upgrade", "head", "--sql",
        cwd=Path(__file__).resolve().parents[2], env=environment,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await asyncio.wait_for(process.communicate(), timeout=30)
    assert process.returncode == 0, "Alembic rejected a synthetic credential with URL delimiters"
    assert b"CREATE TABLE admin_sessions" in stdout
    assert b"CREATE TABLE subscribers" in stdout
    assert password.encode() not in stdout
