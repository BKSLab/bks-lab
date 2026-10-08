"""Note API schemas (see docs/api_contract.md)."""

from datetime import date

from pydantic import BaseModel, Field


class RelatedArticle(BaseModel):
    """Article referenced by a note."""

    slug: str = Field(..., description="Slug of the related article.", examples=["1c-async"])
    title: str = Field(..., description="Title of the related article.")


class Note(BaseModel):
    """Short note for the /notes feed (no dedicated page in v1)."""

    slug: str = Field(..., description="Note slug, used in the #note-<slug> anchor.", examples=["small-team-deploys"])
    title: str = Field(..., description="Note title.")
    excerpt: str = Field(..., description="First paragraph of the note as plain text.")
    published_at: date = Field(..., description="Publication date (ISO 8601).", examples=["2026-02-12"])
    reading_time: int = Field(..., ge=1, description="Reading time in minutes (from word count).", examples=[1])
    tags: list[str] = Field(..., description="Free-form tags.", examples=[["management", "deploy"]])
    related_article: RelatedArticle | None = Field(
        None, description="Linked article; null when `related` is unset or unresolved."
    )
    content_html: str = Field(..., description="Note body rendered to safe HTML (no raw HTML).")
