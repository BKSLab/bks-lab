"""Integration tests for ContentItemRepository on a real database."""

from src.repositories.content_items import ContentItemRepository
from tests.helpers import make_article_item, make_note_item


async def test_sync_type_inserts_new_items(db_session) -> None:
    repository = ContentItemRepository(db_session)

    await repository.sync_type("article", [make_article_item("one"), make_article_item("two")])

    rows = await repository.get_by_type("article")
    assert {row.slug for row in rows} == {"one", "two"}
    row = next(row for row in rows if row.slug == "one")
    assert row.status == "active"
    assert row.category == "development"
    assert row.tags == []
    assert row.reading_time == 1
    assert row.content_hash


async def test_sync_type_skips_unchanged_and_updates_changed(db_session) -> None:
    repository = ContentItemRepository(db_session)
    await repository.sync_type("article", [make_article_item("one")])
    before = (await repository.get_by_type("article"))[0]

    await repository.sync_type(
        "article",
        [make_article_item("one"), make_article_item("one-changed", title="Changed")],
    )

    rows = {row.slug: row for row in await repository.get_by_type("article")}
    assert rows["one"].id == before.id
    assert rows["one-changed"].title == "Changed"


async def test_sync_type_updates_row_when_hash_changes(db_session) -> None:
    repository = ContentItemRepository(db_session)
    await repository.sync_type("article", [make_article_item("one", title="Old title")])

    await repository.sync_type("article", [make_article_item("one", title="New title", text="other body")])

    row = (await repository.get_by_type("article"))[0]
    assert row.title == "New title"
    assert row.content_hash != make_article_item("one", title="Old title").content_hash


async def test_sync_type_deletes_disappeared_items(db_session) -> None:
    repository = ContentItemRepository(db_session)
    await repository.sync_type("note", [make_note_item("keep"), make_note_item("drop")])

    await repository.sync_type("note", [make_note_item("keep")])

    rows = await repository.get_by_type("note")
    assert [row.slug for row in rows] == ["keep"]


async def test_sync_type_maps_draft_status(db_session) -> None:
    repository = ContentItemRepository(db_session)

    await repository.sync_type("article", [make_article_item("draft-one", draft=True)])

    row = (await repository.get_by_type("article"))[0]
    assert row.status == "draft"


async def test_sync_type_is_atomic_per_type(db_session) -> None:
    repository = ContentItemRepository(db_session)
    await repository.sync_type("article", [make_article_item("article")])

    await repository.sync_type("note", [])

    assert len(await repository.get_by_type("article")) == 1
    assert await repository.get_by_type("note") == []
