"""Unit tests for NoteService with mocked repositories."""

from datetime import date
from unittest.mock import AsyncMock

from src.repositories.markdown_content import MarkdownContentRepository
from src.services.notes import NoteService
from tests.helpers import make_article_item, make_note_item


def make_service(notes: list, articles: list) -> NoteService:
    notes_repository = AsyncMock(spec=MarkdownContentRepository)
    notes_repository.get_all.return_value = notes
    articles_repository = AsyncMock(spec=MarkdownContentRepository)
    articles_repository.get_by_slug.side_effect = lambda slug: next(
        (item for item in articles if item.slug == slug), None
    )
    return NoteService(
        notes_repository=notes_repository, articles_repository=articles_repository
    )


NOTES = [
    make_note_item("older-note", published_at=date(2026, 1, 10)),
    make_note_item("newer-note", published_at=date(2026, 2, 10), related="linked-article"),
    make_note_item("broken-link-note", published_at=date(2026, 1, 15), related="missing-article"),
    make_note_item("draft-note", draft=True),
]
ARTICLES = [make_article_item("linked-article", title="Linked article")]


async def test_list_notes_excludes_drafts_and_sorts_desc() -> None:
    service = make_service(NOTES, ARTICLES)

    result = await service.list_notes(page=1, page_size=20)

    assert result.total == 3
    slugs = [item.slug for item in result.items]
    assert slugs[0] == "newer-note"
    assert "draft-note" not in slugs


async def test_list_notes_resolves_related_article() -> None:
    service = make_service(NOTES, ARTICLES)

    result = await service.list_notes(page=1, page_size=20)

    by_slug = {item.slug: item for item in result.items}
    related = by_slug["newer-note"].related_article
    assert related is not None
    assert related.slug == "linked-article"
    assert related.title == "Linked article"
    assert by_slug["broken-link-note"].related_article is None
    assert by_slug["older-note"].related_article is None


async def test_note_excerpt_is_first_paragraph() -> None:
    service = make_service(NOTES, ARTICLES)

    result = await service.list_notes(page=1, page_size=20)

    assert result.items[0].excerpt == "First paragraph of the note."


async def test_get_latest_respects_limit() -> None:
    service = make_service(NOTES, ARTICLES)

    result = await service.get_latest(limit=2)

    assert len(result) == 2
    assert result[0].slug == "newer-note"


async def test_related_draft_article_is_treated_as_missing() -> None:
    notes = [make_note_item("note", related="draft-article")]
    articles = [make_article_item("draft-article", draft=True)]
    service = make_service(notes, articles)

    result = await service.list_notes(page=1, page_size=20)

    assert result.items[0].related_article is None
