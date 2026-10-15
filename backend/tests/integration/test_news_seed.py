"""Startup sync owns source metadata while preserving administrator preferences."""

import asyncio
import os
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.engine import make_url

from scripts.seed_news import CATEGORIES, TOPICS, load_source_profiles, seed_news
from src.db.models import ContentItem, NewsCategory, NewsSource, NewsTopic
from src.news_sources import SourceProfile
from tests.news_helpers import add_source


@pytest.fixture
def profiles():
    return (
        SourceProfile(
            id="verified-one", slug="verified-one", name="Verified One",
            description="Описание первого источника.", homepage_url="https://one.example",
            url="https://one.example/feed", kind="rss",
        ),
        SourceProfile(
            id="verified-two", slug="verified-two", name="Verified Two",
            description="Описание второго источника.", homepage_url="https://two.example",
            url="https://two.example/blog", kind="html",
            config={"item": "article", "title": "h2", "link": "a"},
        ),
    )


async def test_first_seed_registers_supported_sources_paused_and_leaves_content_empty(
    session_factory, db_session, profiles,
):
    counts = await seed_news(session_factory, profiles)
    assert counts == {"sources": 2, "categories": len(CATEGORIES), "topics": len(TOPICS)}
    sources = list(await db_session.scalars(select(NewsSource).order_by(NewsSource.id)))
    assert [source.profile_id for source in sources] == [profile.id for profile in profiles]
    assert all(source.active is False and source.next_check_at is None for source in sources)
    assert sources[0].schedule == profiles[0].default_schedule
    assert await db_session.scalar(select(func.count()).select_from(ContentItem)) == 0


async def test_repeated_seed_performs_no_inserts_or_updates(session_factory, db_engine, profiles):
    await seed_news(session_factory, profiles)
    writes = []

    def capture(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")):
            writes.append(statement)

    event.listen(db_engine.sync_engine, "before_cursor_execute", capture)
    try:
        assert await seed_news(session_factory, profiles) == {"sources": 2, "categories": 0, "topics": 0}
    finally:
        event.remove(db_engine.sync_engine, "before_cursor_execute", capture)
    assert writes == []


async def test_metadata_sync_preserves_user_schedule_enablement_and_taxonomy_edits(
    session_factory, db_session, profiles,
):
    await seed_news(session_factory, profiles)
    source = await db_session.scalar(select(NewsSource).where(NewsSource.profile_id == profiles[0].id))
    identity = source.id, source.slug
    calendar = {"mode": "interval_days", "times": ["09:15"], "every_days": 3, "start_date": "2026-10-15"}
    source.active, source.schedule = True, calendar
    category = await db_session.scalar(select(NewsCategory).where(NewsCategory.name == CATEGORIES[0]))
    category.description, category.active = "Edited category", False
    topic = await db_session.scalar(select(NewsTopic).where(NewsTopic.name == TOPICS[0]))
    topic.description, topic.active = "Edited topic", False
    await db_session.commit()

    updated = replace(profiles[0], name="Updated code name", description="Обновлённое описание.")
    new = replace(profiles[1], id="verified-three", slug="verified-three", url="https://three.example/feed")
    assert await seed_news(session_factory, [updated, profiles[1], new]) == {"sources": 3, "categories": 0, "topics": 0}
    await db_session.refresh(source)
    await db_session.refresh(category)
    await db_session.refresh(topic)
    assert (source.id, source.slug) == identity
    assert source.active is True and source.schedule == calendar
    assert source.next_check_at is not None
    assert source.name == updated.name and source.description == updated.description
    assert category.description == "Edited category" and category.active is False
    assert topic.description == "Edited topic" and topic.active is False


async def test_existing_matching_feed_is_attached_and_removed_profile_keeps_its_row(
    session_factory, db_session, profiles,
):
    source = await add_source(db_session, name="Existing source", url=profiles[0].url)
    source.profile_id = None
    source.schedule = {"mode": "weekly", "times": ["12:30"], "weekdays": [1, 5]}
    await db_session.commit()
    identity, calendar = (source.id, source.slug), dict(source.schedule)
    await seed_news(session_factory, profiles)
    await db_session.refresh(source)
    assert source.profile_id == profiles[0].id
    assert (source.id, source.slug) == identity and source.active and source.schedule == calendar
    await seed_news(session_factory, profiles[1:])
    await db_session.refresh(source)
    assert source.profile_id is None and source.next_check_at is None
    assert source.active and source.schedule == calendar
    assert await db_session.scalar(select(func.count()).select_from(NewsSource)) == 2


async def test_concurrent_seeds_do_not_duplicate_sources_or_taxonomy(session_factory, profiles):
    first, second = await asyncio.gather(
        seed_news(session_factory, profiles), seed_news(session_factory, profiles),
    )
    assert first["sources"] == second["sources"] == len(profiles)
    assert first["categories"] + second["categories"] == len(CATEGORIES)
    assert first["topics"] + second["topics"] == len(TOPICS)
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(NewsSource)) == len(profiles)


async def test_seed_command_repeats_without_resetting_data(postgres_url):
    parsed = make_url(postgres_url)
    environment = {
        **os.environ,
        "POSTGRES_HOST": parsed.host, "POSTGRES_PORT": str(parsed.port),
        "POSTGRES_USER": parsed.username, "POSTGRES_PASSWORD": parsed.password,
        "POSTGRES_DB": parsed.database,
    }
    outputs = []
    for _ in range(2):
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "scripts.seed_news",
            cwd=Path(__file__).resolve().parents[2], env=environment,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=90)
        except TimeoutError:
            process.kill()
            await process.communicate()
            raise
        assert process.returncode == 0, stderr.decode(errors="replace").replace(parsed.password, "***")
        outputs.append(stdout.decode())
    assert f"{len(load_source_profiles())} supported sources" in outputs[0]
    assert "added 0 categories, 0 topics" in outputs[1]
