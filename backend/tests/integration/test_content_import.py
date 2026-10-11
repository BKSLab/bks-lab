"""Integration tests for the one-time Markdown-to-DB content import."""

from pathlib import Path

from scripts.import_content_to_db import import_content
from src.db.models import ContentItem
from src.repositories.content_items import ContentItemRepository
from src.repositories.content_revisions import ContentRevisionRepository
from tests.conftest import write_article

WORDS_PER_MINUTE = 200


async def _rows(session_factory, content_type: str) -> dict[str, ContentItem]:
    async with session_factory() as session:
        items = await ContentItemRepository(session).list_by_type(content_type)
    return {item.slug: item for item in items}


async def _revision_numbers(session_factory, item_id: int) -> list[int]:
    async with session_factory() as session:
        revisions = await ContentRevisionRepository(session).list_for_item(item_id)
    return [revision.revision_no for revision in revisions]


async def test_import_populates_rows_and_first_revisions(
    content_dirs: dict[str, Path], session_factory
) -> None:
    report = await import_content(session_factory, content_dirs["article"].parent, WORDS_PER_MINUTE)

    # 3 valid articles + 4 notes + 4 projects; the invalid file is skipped.
    assert (report.created, report.updated, report.unchanged) == (11, 0, 0)
    assert len(report.errors) == 1
    assert "broken-article.md" in report.errors[0]

    articles = await _rows(session_factory, "article")
    assert set(articles) == {"article-one", "article-two", "article-draft"}
    one = articles["article-one"]
    assert one.title == "First article"
    assert one.content_markdown == "Body text of the test article."
    assert one.content_html.startswith("<p>")
    assert one.content_text == "Body text of the test article."
    assert one.word_count == 6
    assert one.excerpt == "Excerpt of First article"
    assert one.cover_image == "/images/articles/article-one.webp"
    assert one.reading_time == 1
    assert await _revision_numbers(session_factory, one.id) == [1]
    async with session_factory() as session:
        revision = await ContentRevisionRepository(session).get(one.id, 1)
    assert revision is not None
    assert revision.snapshot["content_markdown"] == "Body text of the test article."
    assert revision.snapshot["title"] == "First article"
    assert revision.snapshot["published_at"] == "2026-02-10"


async def test_import_maps_statuses_and_derived_fields(
    content_dirs: dict[str, Path], session_factory
) -> None:
    await import_content(session_factory, content_dirs["article"].parent, WORDS_PER_MINUTE)

    articles = await _rows(session_factory, "article")
    notes = await _rows(session_factory, "note")
    projects = await _rows(session_factory, "project")

    assert articles["article-draft"].status == "draft"
    assert projects["project-archived"].status == "archived"
    assert projects["project-draft"].status == "draft"
    assert projects["project-one"].featured is True
    assert projects["project-one"].sort_order == 1
    assert projects["project-one"].published_at is None
    assert projects["project-one"].reading_time is None
    note = notes["note-two"]
    assert note.related_slug == "article-two"
    assert note.excerpt == "Short note text."
    assert note.category is None


async def test_import_is_idempotent_and_preserves_ids(
    content_dirs: dict[str, Path], session_factory
) -> None:
    first = await import_content(session_factory, content_dirs["article"].parent, WORDS_PER_MINUTE)
    ids_before = {slug: item.id for slug, item in (await _rows(session_factory, "article")).items()}

    second = await import_content(session_factory, content_dirs["article"].parent, WORDS_PER_MINUTE)

    assert (second.created, second.updated, second.unchanged) == (0, 0, first.created)
    assert second.errors == first.errors
    articles = await _rows(session_factory, "article")
    assert {slug: item.id for slug, item in articles.items()} == ids_before
    for item in articles.values():
        assert await _revision_numbers(session_factory, item.id) == [1]


async def test_import_updates_changed_file_and_appends_revision(
    content_dirs: dict[str, Path], session_factory
) -> None:
    await import_content(session_factory, content_dirs["article"].parent, WORDS_PER_MINUTE)
    before = (await _rows(session_factory, "article"))["article-one"]

    write_article(content_dirs["article"], "article-one", title="Renamed article")
    report = await import_content(session_factory, content_dirs["article"].parent, WORDS_PER_MINUTE)

    assert report.updated == 1
    after = (await _rows(session_factory, "article"))["article-one"]
    assert after.id == before.id
    assert after.title == "Renamed article"
    assert after.updated_at >= before.updated_at
    assert await _revision_numbers(session_factory, after.id) == [2, 1]
    async with session_factory() as session:
        latest = await ContentRevisionRepository(session).get(after.id, 2)
    assert latest is not None and latest.snapshot["title"] == "Renamed article"


async def test_import_skips_files_with_invalid_slug(
    content_dirs: dict[str, Path], session_factory
) -> None:
    write_article(content_dirs["article"], "a" * 201)
    write_article(content_dirs["article"], "Invalid_Slug")

    report = await import_content(session_factory, content_dirs["article"].parent, WORDS_PER_MINUTE)

    assert len(report.errors) == 3  # two bad slugs plus the broken fixture file
    assert set(await _rows(session_factory, "article")) == {
        "article-one", "article-two", "article-draft"
    }


async def test_import_respects_reading_time_override(
    content_dirs: dict[str, Path], session_factory
) -> None:
    write_article(
        content_dirs["article"], "override", reading_time=17, body="One short paragraph."
    )

    await import_content(session_factory, content_dirs["article"].parent, WORDS_PER_MINUTE)

    articles = await _rows(session_factory, "article")
    assert articles["override"].reading_time == 17
    assert articles["article-one"].reading_time == 1
