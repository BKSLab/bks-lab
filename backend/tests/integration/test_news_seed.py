"""Startup seed must be incremental, preserve edits and never connect sources."""

import asyncio
import os
import sys
from pathlib import Path

from sqlalchemy import event, func, select
from sqlalchemy.engine import make_url

from scripts.seed_news import CATEGORIES, TOPICS, load_source_catalogue, seed_news
from src.db.models import ContentItem, NewsCategory, NewsSource, NewsSourceCatalogueEntry, NewsTopic
from src.repositories.news_source_catalogue import NewsSourceCatalogueRepository
from tests.news_helpers import add_source


async def test_first_seed_fills_catalogue_but_leaves_sources_and_publications_empty(
    session_factory, db_session,
):
    counts = await seed_news(session_factory, load_source_catalogue())
    assert counts == {"catalogue": 98, "categories": len(CATEGORIES), "topics": len(TOPICS)}
    assert await db_session.scalar(select(func.count()).select_from(NewsSourceCatalogueEntry)) == 98
    assert await db_session.scalar(select(func.count()).select_from(NewsSource)) == 0
    assert await db_session.scalar(select(func.count()).select_from(ContentItem)) == 0


async def test_repeated_seed_performs_no_inserts_or_updates(session_factory, db_engine):
    entries = load_source_catalogue()
    await seed_news(session_factory, entries)
    writes = []

    def capture(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")):
            writes.append(statement)

    event.listen(db_engine.sync_engine, "before_cursor_execute", capture)
    try:
        assert await seed_news(session_factory, entries) == {"catalogue": 0, "categories": 0, "topics": 0}
    finally:
        event.remove(db_engine.sync_engine, "before_cursor_execute", capture)
    assert writes == []


async def test_seed_adds_new_ids_and_preserves_existing_catalogue_and_source_settings(
    session_factory, db_session,
):
    entries = load_source_catalogue()
    await seed_news(session_factory, entries)
    row = await db_session.get(NewsSourceCatalogueEntry, entries[0].id)
    row.data = {**row.data, "description": "Edited research notes"}
    row.position = 500
    category = await db_session.scalar(select(NewsCategory).where(NewsCategory.name == CATEGORIES[0]))
    category.description, category.active = "Edited category", False
    topic = await db_session.scalar(select(NewsTopic).where(NewsTopic.name == TOPICS[0]))
    topic.description, topic.active = "Edited topic", False
    await db_session.commit()
    source = await add_source(db_session, name="Checked source")
    source.active, source.interval_hours = False, 12
    await db_session.commit()
    custom = entries[0].model_copy(update={"id": "editor-suggestion", "name": "Custom suggestion"})
    await NewsSourceCatalogueRepository(db_session).seed([
        {"id": custom.id, "position": 600, "data": custom.model_dump(by_alias=True)},
    ])
    new = entries[0].model_copy(update={"id": "new-research-entry"})
    assert await seed_news(session_factory, [*entries, new]) == {"catalogue": 1, "categories": 0, "topics": 0}
    await db_session.refresh(row)
    await db_session.refresh(category)
    await db_session.refresh(topic)
    await db_session.refresh(source)
    assert row.data["description"] == "Edited research notes" and row.position == 500
    assert category.description == "Edited category" and category.active is False
    assert topic.description == "Edited topic" and topic.active is False
    assert source.name == "Checked source" and source.active is False and source.interval_hours == 12
    assert (await db_session.get(NewsSourceCatalogueEntry, custom.id)).data["name"] == "Custom suggestion"
    assert await db_session.scalar(select(func.count()).select_from(NewsSourceCatalogueEntry)) == 100
    assert await db_session.scalar(select(func.count()).select_from(NewsSource)) == 1


async def test_concurrent_seeds_do_not_duplicate_catalogue_or_taxonomy(session_factory):
    entries = load_source_catalogue()
    first, second = await asyncio.gather(
        seed_news(session_factory, entries), seed_news(session_factory, entries),
    )
    assert first["catalogue"] + second["catalogue"] == len(entries)
    assert first["categories"] + second["categories"] == len(CATEGORIES)
    assert first["topics"] + second["topics"] == len(TOPICS)
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(NewsSourceCatalogueEntry)) == len(entries)


async def test_seed_command_reports_zero_additions_on_repeat(postgres_url):
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
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
        assert process.returncode == 0, stderr.decode(errors="replace").replace(parsed.password, "***")
        outputs.append(stdout.decode())
    assert "98 catalogue entries" in outputs[0]
    assert "0 catalogue entries, 0 categories, 0 topics" in outputs[1]
