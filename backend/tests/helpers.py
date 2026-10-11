"""Helpers for building ContentItem fixtures without touching the database."""

from datetime import date

from src.db.models import ContentItem
from src.utils.markdown import reading_time_minutes


def _item(content_type: str, slug: str, **overrides) -> ContentItem:
    values = {
        "type": content_type,
        "slug": slug,
        "title": "Test item",
        "category": None,
        "tags": [],
        "published_at": None,
        "reading_time": None,
        "status": "active",
        "word_count": 0,
        "content_text": "",
        "excerpt": None,
        "cover_image": None,
        "seo_title": None,
        "seo_description": None,
        "og_image": None,
        "related_slug": None,
        "featured": False,
        "sort_order": None,
        "content_markdown": "",
        "content_html": "",
    }
    values.update(overrides)
    return ContentItem(**values)


def make_article_item(
    slug: str = "test-article",
    *,
    title: str = "Test article",
    category: str = "development",
    published_at: date = date(2026, 2, 10),
    draft: bool = False,
    text: str = "Some article body words.",
    tags: list[str] | None = None,
) -> ContentItem:
    """Build an article ContentItem with derived fields like the importer does."""
    word_count = len(text.split())
    return _item(
        "article",
        slug,
        title=title,
        category=category,
        tags=tags or [],
        published_at=published_at,
        reading_time=reading_time_minutes(word_count),
        status="draft" if draft else "active",
        word_count=word_count,
        content_text=text,
        excerpt=f"Excerpt of {title}",
        cover_image=f"/images/articles/{slug}.webp",
        content_markdown=text,
        content_html=f"<p>{text}</p>",
    )


def make_note_item(
    slug: str = "test-note",
    *,
    title: str = "Test note",
    published_at: date = date(2026, 2, 12),
    related: str | None = None,
    draft: bool = False,
    text: str = "First paragraph of the note.\nSecond paragraph.",
) -> ContentItem:
    """Build a note ContentItem with derived fields like the importer does."""
    word_count = len(text.split())
    return _item(
        "note",
        slug,
        title=title,
        published_at=published_at,
        reading_time=reading_time_minutes(word_count),
        status="draft" if draft else "active",
        word_count=word_count,
        content_text=text,
        excerpt=text.split("\n")[0],
        related_slug=related,
        content_markdown=text,
        content_html=f"<p>{text}</p>",
    )


def make_project_item(
    slug: str = "test-project",
    *,
    title: str = "Test project",
    project_status: str = "active",
    featured: bool = False,
    order: int = 10,
    draft: bool = False,
) -> ContentItem:
    """Build a project ContentItem with derived fields like the importer does."""
    status = "draft" if draft else project_status
    return _item(
        "project",
        slug,
        title=title,
        tags=["FastAPI"],
        status=status,
        excerpt=f"Excerpt of {title}",
        cover_image=f"/images/projects/{slug}.webp",
        featured=featured,
        sort_order=order,
        content_markdown="Project body",
        content_html="<p>Project body</p>",
        content_text="Project body",
        word_count=2,
    )
