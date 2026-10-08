"""ORM model for the content read-model projection.

`content_items` mirrors Markdown files from `content/` (the source of truth)
into PostgreSQL for the admin panel and future agent-based analysis.
Rows are managed exclusively by the content sync; direct edits are overwritten.
"""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.db.models.base import Base

TagsList = JSONB()


class ContentItem(Base):
    """Projection of one Markdown content file."""

    __tablename__ = "content_items"

    __table_args__ = (
        UniqueConstraint("type", "slug", name="uq_content_items_type_slug"),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        comment="Unique identifier of the content item.",
    )
    type: Mapped[str] = mapped_column(
        String(length=20),
        nullable=False,
        comment="Content type: article | note | project.",
    )
    slug: Mapped[str] = mapped_column(
        String(length=200),
        nullable=False,
        comment="Slug from the file name; unique within the type.",
    )
    title: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Title from frontmatter.",
    )
    category: Mapped[str | None] = mapped_column(
        String(length=50),
        nullable=True,
        comment="Blog category slug; only articles have one.",
    )
    tags: Mapped[list] = mapped_column(
        TagsList,
        nullable=False,
        default=list,
        comment="Free-form tags as a JSON array.",
    )
    published_at: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Publication date; null for projects (not dated).",
    )
    reading_time: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Reading time in minutes; articles and notes only.",
    )
    status: Mapped[str] = mapped_column(
        String(length=20),
        nullable=False,
        comment="Projection status: active | draft | archived (archived is projects-only).",
    )
    word_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Word count of the plain-text body.",
    )
    content_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Plain-text body extracted from Markdown (for analysis).",
    )
    content_hash: Mapped[str] = mapped_column(
        String(length=64),
        nullable=False,
        comment="SHA-256 of the raw file; unchanged files are skipped on sync.",
    )
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="When the row was last written by the content sync.",
    )

    def __repr__(self) -> str:
        return f"<ContentItem(id={self.id}, type='{self.type}', slug='{self.slug}')>"
