"""Integration tests for ContentRevisionRepository on a real database."""

import pytest
from sqlalchemy.exc import IntegrityError

from src.db.models import ContentRevision
from src.repositories.content_items import ContentItemRepository
from src.repositories.content_revisions import ContentRevisionRepository
from tests.helpers import make_article_item


def values_of(item) -> dict:
    """Column values of a transient ContentItem, ready for repository.create."""
    return {key: value for key, value in vars(item).items() if not key.startswith("_")}


async def test_create_assigns_sequential_revision_numbers(db_session) -> None:
    items = ContentItemRepository(db_session)
    revisions = ContentRevisionRepository(db_session)
    item = await items.create(values_of(make_article_item("one")))

    first = await revisions.create(item_id=item.id, snapshot={"title": "v1"}, word_count=3)
    second = await revisions.create(item_id=item.id, snapshot={"title": "v2"}, word_count=4)

    assert first.revision_no == 1
    assert second.revision_no == 2
    assert second.created_at is not None


async def test_list_for_item_returns_newest_first(db_session) -> None:
    items = ContentItemRepository(db_session)
    revisions = ContentRevisionRepository(db_session)
    item = await items.create(values_of(make_article_item("one")))
    other = await items.create(values_of(make_article_item("two")))
    await revisions.create(item_id=item.id, snapshot={"title": "v1"}, word_count=3)
    await revisions.create(item_id=item.id, snapshot={"title": "v2"}, word_count=4)
    await revisions.create(item_id=other.id, snapshot={"title": "other"}, word_count=1)

    rows = await revisions.list_for_item(item.id)

    assert [row.revision_no for row in rows] == [2, 1]
    assert all(row.item_id == item.id for row in rows)


async def test_get_returns_exact_revision_or_none(db_session) -> None:
    items = ContentItemRepository(db_session)
    revisions = ContentRevisionRepository(db_session)
    item = await items.create(values_of(make_article_item("one")))
    await revisions.create(item_id=item.id, snapshot={"title": "v1"}, word_count=3)

    found = await revisions.get(item.id, 1)

    assert found is not None
    assert found.snapshot == {"title": "v1"}
    assert found.word_count == 3
    assert await revisions.get(item.id, 99) is None
    assert await revisions.get(999999, 1) is None


async def test_duplicate_revision_no_is_rejected_by_the_unique_index(db_session) -> None:
    items = ContentItemRepository(db_session)
    revisions = ContentRevisionRepository(db_session)
    item = await items.create(values_of(make_article_item("one")))
    await revisions.create(item_id=item.id, snapshot={"title": "v1"}, word_count=3)

    db_session.add(
        ContentRevision(item_id=item.id, revision_no=1, snapshot={"title": "dup"}, word_count=1)
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()
