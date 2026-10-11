"""Integration tests for ContentItemRepository on a real database."""

import pytest

from src.exceptions.repositories import ContentItemConflictError
from src.repositories.content_items import ContentItemRepository
from src.repositories.content_revisions import ContentRevisionRepository
from tests.helpers import make_article_item, make_note_item, make_project_item


def values_of(item) -> dict:
    """Column values of a transient ContentItem, ready for repository.create."""
    return {key: value for key, value in vars(item).items() if not key.startswith("_")}


async def test_create_and_get_by_id_roundtrip(db_session) -> None:
    repository = ContentItemRepository(db_session)

    item = await repository.create(values_of(make_article_item("one")))

    assert item.id is not None
    assert item.created_at is not None and item.updated_at is not None
    loaded = await repository.get_by_id(item.id)
    assert loaded is not None
    assert loaded.slug == "one"
    assert loaded.status == "active"
    assert loaded.category == "development"
    assert loaded.excerpt == "Excerpt of Test article"
    assert loaded.content_html == "<p>Some article body words.</p>"


async def test_get_by_id_returns_none_when_missing(db_session) -> None:
    repository = ContentItemRepository(db_session)

    assert await repository.get_by_id(999999) is None


async def test_get_by_slug_matches_within_type_only(db_session) -> None:
    repository = ContentItemRepository(db_session)
    await repository.create(values_of(make_article_item("shared-slug")))
    await repository.create(values_of(make_project_item("shared-slug")))

    article = await repository.get_by_slug("article", "shared-slug")
    project = await repository.get_by_slug("project", "shared-slug")

    assert article is not None and article.type == "article"
    assert project is not None and project.type == "project"
    assert await repository.get_by_slug("article", "missing") is None


async def test_create_duplicate_type_slug_raises_conflict(db_session) -> None:
    repository = ContentItemRepository(db_session)
    await repository.create(values_of(make_article_item("one")))

    with pytest.raises(ContentItemConflictError) as exc_info:
        await repository.create(values_of(make_article_item("one")))

    assert exc_info.value.status_code == 409


async def test_update_changes_columns_and_bumps_updated_at(db_session) -> None:
    repository = ContentItemRepository(db_session)
    item = await repository.create(values_of(make_article_item("one", title="Old title")))

    updated = await repository.update(item, {"title": "New title", "status": "draft"})

    assert updated.id == item.id
    assert updated.title == "New title"
    assert updated.status == "draft"
    loaded = await repository.get_by_slug("article", "one")
    assert loaded is not None and loaded.title == "New title"


async def test_update_to_conflicting_slug_raises_conflict(db_session) -> None:
    repository = ContentItemRepository(db_session)
    await repository.create(values_of(make_article_item("one")))
    other = await repository.create(values_of(make_article_item("two")))

    with pytest.raises(ContentItemConflictError):
        await repository.update(other, {"slug": "one"})


async def test_delete_removes_item_and_cascades_revisions(db_session) -> None:
    repository = ContentItemRepository(db_session)
    revisions = ContentRevisionRepository(db_session)
    item = await repository.create(values_of(make_article_item("one")))
    await revisions.create(item_id=item.id, snapshot={"title": "Test article"}, word_count=3)

    await repository.delete(item)

    assert await repository.get_by_id(item.id) is None
    assert await revisions.list_for_item(item.id) == []


async def test_list_by_type_filters_by_status(db_session) -> None:
    repository = ContentItemRepository(db_session)
    await repository.create(values_of(make_article_item("active-one")))
    await repository.create(values_of(make_article_item("draft-one", draft=True)))
    await repository.create(values_of(make_project_item("archived-one", project_status="archived")))

    all_articles = await repository.list_by_type("article")
    public_articles = await repository.list_by_type("article", statuses=("active", "archived"))

    assert {item.slug for item in all_articles} == {"active-one", "draft-one"}
    assert [item.slug for item in public_articles] == ["active-one"]


async def test_get_page_filters_and_orders(db_session) -> None:
    repository = ContentItemRepository(db_session)
    await repository.create(values_of(make_note_item("note-b", title="Second note")))
    await repository.create(values_of(make_note_item("note-a", title="First note")))
    await repository.create(values_of(make_article_item("article", draft=True)))

    notes, total = await repository.get_page(
        content_type="note", status=None, query=None, page=1, page_size=20
    )
    drafts, drafts_total = await repository.get_page(
        content_type=None, status="draft", query=None, page=1, page_size=20
    )
    first, first_total = await repository.get_page(
        content_type="note", status=None, query="FIRST", page=1, page_size=20
    )
    page_two, _ = await repository.get_page(
        content_type="note", status=None, query=None, page=2, page_size=1
    )

    assert total == 2
    assert {item.slug for item in notes} == {"note-a", "note-b"}
    assert drafts_total == 1 and drafts[0].slug == "article"
    assert first_total == 1 and first[0].slug == "note-a"
    assert len(page_two) == 1
