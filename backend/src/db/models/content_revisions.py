"""ORM model for content version snapshots.

Every successful save (and the one-time import) appends one row per
material; a rollback copies a snapshot back into `content_items` and records
it as a new revision, so history is never rewritten.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.db.models.base import Base


class ContentRevision(Base):
    """Immutable snapshot of one save of a content item."""

    __tablename__ = "content_revisions"

    __table_args__ = (
        Index("uq_content_revisions_item_revision", "item_id", "revision_no", unique=True),
        Index("ix_content_revisions_item_id", "item_id"),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        comment="Unique identifier of the revision.",
    )
    item_id: Mapped[int] = mapped_column(
        ForeignKey("content_items.id", ondelete="CASCADE"),
        nullable=False,
        doc="Material this snapshot belongs to.",
        comment="FK to content_items; revisions are deleted with the material.",
    )
    revision_no: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Version number within the material, starting at 1.",
        comment="Sequential version number within the material.",
    )
    snapshot: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        doc="All editable fields including content_markdown.",
        comment="Snapshot of all editable fields, including the Markdown body.",
    )
    word_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Word count at save time; shown in the version list.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="When this version was saved.",
    )

    def __repr__(self) -> str:
        return f"<ContentRevision(id={self.id}, item_id={self.item_id}, revision_no={self.revision_no})>"
