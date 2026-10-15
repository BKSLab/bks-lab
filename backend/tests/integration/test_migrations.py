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
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=120)
        except TimeoutError:
            if process.returncode is None:
                process.kill()
            await process.communicate()
            raise
        assert process.returncode == 0, (stdout + stderr).decode(errors="replace").replace(parsed.password, "***")

    await alembic("upgrade", "0009")
    engine = create_async_engine(parsed.set(database="migration_check"))
    async with engine.begin() as connection:
        await connection.execute(text("""
            INSERT INTO news_sources
                (slug, name, url, kind, config, active, priority, trust_score,
                 vendor_affiliated, interval_hours, cursor, last_new_count, health)
            VALUES
                ('retained-source', 'Retained source', 'https://retained.example/feed',
                 'rss', '{}', true, 75, 80, false, 6,
                 '{"initial_cutoff_at":"2026-09-15T04:00:00+00:00"}', 7, 'ok')
        """))
    await alembic("upgrade", "0010")
    async with engine.begin() as connection:
        await connection.execute(text("""
            INSERT INTO content_items
                (type, slug, title, tags, published_at, status, word_count,
                 content_text, content_markdown, content_html, featured)
            VALUES
                ('note', 'retained-note', 'Retained note', '[]', '2026-10-14',
                 'active', 2, 'Original text', 'Original text', '<p>Original text</p>', false)
        """))
    await alembic("upgrade", "head")
    async with engine.connect() as connection:
        retained = (await connection.execute(text(
            "SELECT slug, active, cursor, last_new_count, profile_id, description, schedule FROM news_sources"
        ))).mappings().one()
        assert retained["slug"] == "retained-source" and retained["active"] is True
        assert retained["cursor"] == {"initial_cutoff_at": "2026-09-15T04:00:00+00:00"}
        assert retained["last_new_count"] == 7 and retained["profile_id"] is None
        assert retained["description"] == "" and retained["schedule"]["mode"] == "daily"
        note = (await connection.execute(text(
            "SELECT slug, content_markdown, status, published_at_time, source_url FROM content_items"
        ))).mappings().one()
        assert note["slug"] == "retained-note" and note["content_markdown"] == "Original text"
        assert note["status"] == "active" and note["published_at_time"] is None and note["source_url"] is None
        assert await connection.scalar(text("SELECT count(*) FROM news_note_queue")) == 0
    await alembic("downgrade", "0010")
    async with engine.connect() as connection:
        assert await connection.scalar(text("SELECT content_markdown FROM content_items WHERE slug = 'retained-note'")) == "Original text"
    await alembic("upgrade", "head")
    await engine.dispose()
    await alembic("check")
    await alembic("downgrade", "0001")
    engine = create_async_engine(parsed.set(database="migration_check"))
    async with engine.connect() as connection:
        names = await connection.run_sync(lambda conn: inspect(conn).get_table_names())
        assert "content_items" in names and "page_views" in names
        assert "admin_sessions" not in names and "subscribers" not in names
        assert "feedback_messages" not in names
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
    try:
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=120)
    except TimeoutError:
        if process.returncode is None:
            process.kill()
        await process.communicate()
        raise
    assert process.returncode == 0, "Alembic rejected a synthetic credential with URL delimiters"
    assert b"CREATE TABLE admin_sessions" in stdout
    assert b"CREATE TABLE subscribers" in stdout
    assert b"CREATE TABLE feedback_messages" in stdout
    assert password.encode() not in stdout
