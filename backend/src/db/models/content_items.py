"""ORM model for the primary content storage.

`content_items` is the source of truth for articles, notes and projects:
the full metadata set plus the source Markdown body and its rendered HTML.
Existing Markdown files under `content/` are imported once by
`scripts/import_content_to_db.py`; revisions live in `content_revisions`.
"""

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Integer, String, Text, UniqueConstraint, false, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.models.base import Base

TagsList = JSONB()


class ContentItem(Base):
    """One content item (article, note or project) stored in PostgreSQL."""

    __tablename__ = "content_items"

    __table_args__ = (
        UniqueConstraint("type", "slug", name="uq_content_items_type_slug"),
    )

    # Fetch server-generated timestamps (created_at/updated_at) via RETURNING
    # on both INSERT and UPDATE, so readers never trigger a lazy refresh.
    __mapper_args__ = {"eager_defaults": True}

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
        comment="URL slug; unique within the type.",
    )
    title: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Material title.",
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
        comment="Publication status: active | draft | archived (archived is projects-only).",
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
    excerpt: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Annotation; notes store the first paragraph computed on write.",
    )
    cover_image: Mapped[str | None] = mapped_column(
        String(length=500),
        nullable=True,
        comment="Cover image path (/images/... or /uploads/...).",
    )
    seo_title: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="SEO title override; defaults to the title.",
    )
    seo_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="SEO description override; defaults to the excerpt.",
    )
    og_image: Mapped[str | None] = mapped_column(
        String(length=500),
        nullable=True,
        comment="Open Graph image override.",
    )
    related_slug: Mapped[str | None] = mapped_column(
        String(length=200),
        nullable=True,
        comment="Notes only: slug of the related article.",
    )
    featured: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        comment="Projects: shown on the home page when true.",
    )
    sort_order: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Projects: explicit ordering on the home page.",
    )
    # Nullable at the DDL level only: rows created before the one-time import
    # have no body yet. Writers (importer now, admin API later) always fill it.
    content_markdown: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Source Markdown body.",
    )
    content_html: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Rendered HTML cache; produced on write, never on read.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="When the material was created.",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="When the material was last saved.",
    )

    revisions: Mapped[list["ContentRevision"]] = relationship(
        cascade="all, delete-orphan",
        passive_deletes=True,
        doc="Version snapshots; removed by the ON DELETE CASCADE foreign key.",
    )

    def __repr__(self) -> str:
        return f"<ContentItem(id={self.id}, type='{self.type}', slug='{self.slug}')>"
