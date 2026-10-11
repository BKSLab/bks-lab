"""Derivation of stored content fields from editable input.

Single source of truth shared by the admin save path (ContentAdminService)
and the one-time Markdown importer (scripts/import_content_to_db.py): both
normalize their input into ContentFields and derive the same column set.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from src.utils import markdown as md


@dataclass(frozen=True)
class ContentFields:
    """Editable fields of one material, normalized across input channels.

    `status` is the resolved storage status (draft | active | archived);
    `reading_time_override` is the optional explicit reading time.
    """

    title: str
    status: str
    content_markdown: str
    category: str | None = None
    tags: list[str] = field(default_factory=list)
    published_at: date | None = None
    excerpt: str | None = None
    cover_image: str | None = None
    seo_title: str | None = None
    seo_description: str | None = None
    og_image: str | None = None
    related_slug: str | None = None
    featured: bool = False
    sort_order: int | None = None
    reading_time_override: int | None = None


def resolve_status(*, draft: bool, lifecycle: str | None = None) -> str:
    """Map draft/archived flags to the storage status (docs/content_format.md)."""
    if draft:
        return "draft"
    if lifecycle == "archived":
        return "archived"
    return "active"


def build_item_values(
    content_type: str, slug: str, fields: ContentFields, words_per_minute: int
) -> dict[str, Any]:
    """Compute the full content_items column set from editable fields.

    Notes never carry an explicit excerpt: it is derived from the first
    paragraph of the body. The same fallback applies when excerpt is empty.
    Reading time: explicit override wins; projects have none; articles and
    notes derive it from the word count.
    """
    content_text = md.extract_plain_text(fields.content_markdown)
    word_count = md.count_words(content_text)
    if fields.reading_time_override is not None:
        reading_time: int | None = fields.reading_time_override
    elif content_type == "project":
        reading_time = None
    else:
        reading_time = md.reading_time_minutes(word_count, words_per_minute)
    return {
        "type": content_type,
        "slug": slug,
        "title": fields.title,
        "category": fields.category,
        "tags": list(fields.tags),
        "published_at": fields.published_at,
        "reading_time": reading_time,
        "status": fields.status,
        "word_count": word_count,
        "content_text": content_text,
        "excerpt": fields.excerpt or md.extract_excerpt(fields.content_markdown),
        "cover_image": fields.cover_image,
        "seo_title": fields.seo_title,
        "seo_description": fields.seo_description,
        "og_image": fields.og_image,
        "related_slug": fields.related_slug,
        "featured": fields.featured,
        "sort_order": fields.sort_order,
        "content_markdown": fields.content_markdown,
        "content_html": md.render_markdown(fields.content_markdown),
    }


def build_snapshot(values: dict[str, Any]) -> dict[str, Any]:
    """Build a JSON-safe revision snapshot of all editable and derived fields."""
    snapshot = {key: value for key, value in values.items() if key not in {"type", "slug"}}
    if snapshot["published_at"] is not None:
        snapshot["published_at"] = snapshot["published_at"].isoformat()
    return snapshot


def snapshot_to_values(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Restore content_items column values from a revision snapshot."""
    values = dict(snapshot)
    if values.get("published_at"):
        values["published_at"] = date.fromisoformat(values["published_at"])
    return values
