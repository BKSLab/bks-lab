"""Helpers for building ParsedContent fixtures without touching the filesystem."""

from datetime import date

from src.repositories.markdown_content import ParsedContent
from src.schemas.frontmatter import ArticleFrontmatter, NoteFrontmatter, ProjectFrontmatter
from src.utils.markdown import content_hash, reading_time_minutes


def make_article_item(
    slug: str = "test-article",
    *,
    title: str = "Test article",
    category: str = "development",
    published_at: date = date(2026, 2, 10),
    draft: bool = False,
    text: str = "Some article body words.",
    tags: list[str] | None = None,
) -> ParsedContent:
    frontmatter = ArticleFrontmatter(
        title=title,
        excerpt=f"Excerpt of {title}",
        category=category,
        published_at=published_at,
        cover_image=f"/images/articles/{slug}.webp",
        tags=tags or [],
        draft=draft,
    )
    word_count = len(text.split())
    return ParsedContent(
        content_type="article",
        slug=slug,
        frontmatter=frontmatter,
        status="draft" if draft else "active",
        content_html=f"<p>{text}</p>",
        content_text=text,
        excerpt=text,
        word_count=word_count,
        reading_time=reading_time_minutes(word_count),
        content_hash=content_hash(text),
    )


def make_note_item(
    slug: str = "test-note",
    *,
    title: str = "Test note",
    published_at: date = date(2026, 2, 12),
    related: str | None = None,
    draft: bool = False,
    text: str = "First paragraph of the note.\nSecond paragraph.",
) -> ParsedContent:
    frontmatter = NoteFrontmatter(
        title=title,
        published_at=published_at,
        tags=[],
        related=related,
        draft=draft,
    )
    word_count = len(text.split())
    return ParsedContent(
        content_type="note",
        slug=slug,
        frontmatter=frontmatter,
        status="draft" if draft else "active",
        content_html=f"<p>{text}</p>",
        content_text=text,
        excerpt=text.split("\n")[0],
        word_count=word_count,
        reading_time=reading_time_minutes(word_count),
        content_hash=content_hash(text),
    )


def make_project_item(
    slug: str = "test-project",
    *,
    title: str = "Test project",
    project_status: str = "active",
    featured: bool = False,
    order: int = 10,
    draft: bool = False,
) -> ParsedContent:
    frontmatter = ProjectFrontmatter(
        title=title,
        excerpt=f"Excerpt of {title}",
        cover_image=f"/images/projects/{slug}.webp",
        tags=["FastAPI"],
        status=project_status,
        featured=featured,
        order=order,
        draft=draft,
    )
    status = "draft" if draft else ("archived" if project_status == "archived" else "active")
    return ParsedContent(
        content_type="project",
        slug=slug,
        frontmatter=frontmatter,
        status=status,
        content_html="<p>Project body</p>",
        content_text="Project body",
        excerpt="Project body",
        word_count=2,
        reading_time=None,
        content_hash=content_hash(slug),
    )
