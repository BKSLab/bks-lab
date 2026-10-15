"""Unit tests for ContentAdminService with mocked repositories."""

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock

import pytest

from src.clients.revalidation import RevalidationClient
from src.db.models import ContentItem, ContentRevision
from src.exceptions.admin import AdminContentNotFoundError, ContentValidationError
from src.exceptions.repositories import ContentItemConflictError, ContentRevisionRepositoryError
from src.repositories.content_items import ContentItemRepository
from src.repositories.content_revisions import ContentRevisionRepository
from src.repositories.news_notes import NewsNoteRepository
from src.schemas.admin import ArticleCreate, ContentPatch
from src.services.content_admin import ContentAdminService
from src.services.content_fields import build_item_values, build_snapshot, ContentFields
from tests.helpers import make_article_item, make_project_item

NOW = datetime(2026, 2, 20, 12, 0, 0, tzinfo=timezone.utc)


def stamp(item: ContentItem) -> ContentItem:
    """Fill server-generated fields the way a flushed row would have them."""
    item.id = item.id or 1
    item.created_at = item.created_at or NOW
    item.updated_at = item.updated_at or NOW
    return item


def make_service(item: ContentItem | None = None):
    items = AsyncMock(spec=ContentItemRepository)
    items.get_by_id.return_value = item
    items.add.side_effect = lambda values: stamp(ContentItem(**values))

    async def apply(target, values):
        for key, value in values.items():
            setattr(target, key, value)
        return target

    items.apply.side_effect = apply
    revisions = AsyncMock(spec=ContentRevisionRepository)
    revalidator = AsyncMock(spec=RevalidationClient)
    service = ContentAdminService(
        items=items, revisions=revisions, revalidator=revalidator, words_per_minute=200,
        utc_now=lambda: NOW, note_queue=AsyncMock(spec=NewsNoteRepository),
    )
    return service, items, revisions, revalidator


def article_payload(**overrides) -> ArticleCreate:
    return ArticleCreate(
        **{
            "type": "article",
            "slug": "new-article",
            "title": "New article",
            "excerpt": "Excerpt of the new article",
            "category": "development",
            "published_at": date(2026, 2, 20),
            "cover_image": "/images/articles/new-article.webp",
            "content_markdown": "Body of the new article.",
            **overrides,
        }
    )


async def test_create_item_writes_row_revision_and_revalidates() -> None:
    service, items, revisions, revalidator = make_service()

    result = await service.create_item(article_payload())

    assert result.slug == "new-article"
    assert result.status == "draft"  # materials are created as drafts by default
    assert result.content_markdown == "Body of the new article."
    items.add.assert_called_once()
    revisions.add.assert_called_once()
    snapshot = revisions.add.call_args.kwargs["snapshot"]
    assert snapshot["content_markdown"] == "Body of the new article."
    assert snapshot["status"] == "draft"
    items.commit.assert_called_once()
    revalidator.revalidate_content.assert_called_once()


async def test_create_item_conflict_aborts_before_revision_and_webhook() -> None:
    service, items, revisions, revalidator = make_service()
    items.add.side_effect = ContentItemConflictError("duplicate")

    with pytest.raises(ContentItemConflictError) as exc_info:
        await service.create_item(article_payload())

    assert exc_info.value.status_code == 409
    revisions.add.assert_not_called()
    items.commit.assert_not_called()
    revalidator.revalidate_content.assert_not_called()


async def test_update_item_is_atomic_when_revision_write_fails() -> None:
    service, items, revisions, revalidator = make_service(stamp(make_article_item("one")))
    revisions.add.side_effect = ContentRevisionRepositoryError("revision storage failed")

    with pytest.raises(ContentRevisionRepositoryError):
        await service.update_item(1, ContentPatch(title="Renamed"))

    items.apply.assert_called_once()
    items.commit.assert_not_called()
    revalidator.revalidate_content.assert_not_called()


async def test_update_item_merges_patch_and_records_revision() -> None:
    service, items, revisions, revalidator = make_service(stamp(make_article_item("one")))

    result = await service.update_item(1, ContentPatch(title="Renamed title"))

    assert result.title == "Renamed title"
    assert result.slug == "one"  # slug is immutable
    assert revisions.add.call_args.kwargs["snapshot"]["title"] == "Renamed title"
    items.commit.assert_called_once()


async def test_update_item_rejects_state_invalid_for_the_type() -> None:
    service, *_ = make_service(stamp(make_project_item("proj")))

    with pytest.raises(ContentValidationError) as exc_info:
        await service.update_item(1, ContentPatch(tags=[]))

    assert exc_info.value.status_code == 422


async def test_update_item_raises_not_found_for_missing_material() -> None:
    service, *_ = make_service(item=None)

    with pytest.raises(AdminContentNotFoundError) as exc_info:
        await service.update_item(999, ContentPatch(title="x"))

    assert exc_info.value.status_code == 404


async def test_set_status_rejects_archived_for_non_projects() -> None:
    service, items, revisions, _ = make_service(stamp(make_article_item("one")))

    with pytest.raises(ContentValidationError) as exc_info:
        await service.set_status(1, "archived")

    assert exc_info.value.status_code == 422
    items.apply.assert_not_called()
    revisions.add.assert_not_called()


async def test_set_status_allows_archived_for_projects_and_snapshots() -> None:
    service, items, revisions, _ = make_service(stamp(make_project_item("proj")))

    result = await service.set_status(1, "archived")

    assert result.status == "archived"
    items.apply.assert_called_once()
    snapshot = revisions.add.call_args.kwargs["snapshot"]
    assert snapshot["status"] == "archived"
    assert snapshot["content_markdown"]


async def test_restore_revision_rewrites_row_and_appends_new_revision() -> None:
    item = stamp(make_article_item("one", title="Current title"))
    service, items, revisions, _ = make_service(item)
    old_values = build_item_values(
        "article",
        "one",
        ContentFields(
            title="Old title",
            status="active",
            content_markdown="Old body.",
            category="development",
            published_at=date(2026, 2, 10),
            excerpt="Old excerpt",
            cover_image="/images/articles/one.webp",
        ),
        200,
    )
    snapshot = build_snapshot(old_values)
    revisions.get.return_value = ContentRevision(
        item_id=1, revision_no=1, snapshot=snapshot, word_count=2, created_at=NOW
    )

    result = await service.restore_revision(1, 1)

    assert result.title == "Old title"
    assert result.content_markdown == "Old body."
    new_revision = revisions.add.call_args.kwargs
    assert new_revision["snapshot"] == {**snapshot, "published_at_time": None, "source_name": None, "source_url": None}
    items.commit.assert_called_once()


async def test_restore_revision_raises_not_found_for_missing_version() -> None:
    service, _, revisions, _ = make_service(stamp(make_article_item("one")))
    revisions.get.return_value = None

    with pytest.raises(AdminContentNotFoundError):
        await service.restore_revision(1, 42)


async def test_get_revision_raises_not_found_for_missing_material_or_version() -> None:
    service, _, revisions, _ = make_service(stamp(make_article_item("one")))
    revisions.get.return_value = None

    with pytest.raises(AdminContentNotFoundError):
        await service.get_revision(1, 5)

    service_without_item, *_ = make_service(item=None)
    with pytest.raises(AdminContentNotFoundError):
        await service_without_item.get_revision(999, 1)


async def test_delete_item_commits_and_revalidates() -> None:
    service, items, _, revalidator = make_service(stamp(make_article_item("one")))

    await service.delete_item(1)

    items.remove.assert_called_once()
    items.commit.assert_called_once()
    revalidator.revalidate_content.assert_called_once()
