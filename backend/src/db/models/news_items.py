"""Collected source material; independent of the published Markdown read model."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.models.base import Base

if TYPE_CHECKING:
    from src.db.models.news_analyses import NewsAnalysis, NewsEditorialDecision
    from src.db.models.news_sources import NewsSource


class NewsItem(Base):
    __tablename__ = "news_items"
    __table_args__ = (
        UniqueConstraint(
            "source_id", "external_id", name="uq_news_items_source_external"
        ),
        UniqueConstraint(
            "source_id", "normalized_url", name="uq_news_items_source_url"
        ),
        CheckConstraint(
            "status IN ('pending_analysis', 'analyzed')", name="ck_news_items_status"
        ),
        Index("ix_news_items_status_seen", "status", "first_seen_at"),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True, doc="Item ID.", comment="Item ID."
    )
    source_id: Mapped[int] = mapped_column(
        ForeignKey("news_sources.id", ondelete="CASCADE"),
        index=True,
        doc="Owning source.",
        comment="Owning source.",
    )
    external_id: Mapped[str | None] = mapped_column(
        String(1000),
        doc="RSS GUID or provider identifier.",
        comment="RSS GUID or provider identifier.",
    )
    url: Mapped[str] = mapped_column(
        Text, doc="Original article URL.", comment="Original article URL."
    )
    canonical_url: Mapped[str | None] = mapped_column(
        Text, doc="Canonical article URL.", comment="Canonical article URL."
    )
    normalized_url: Mapped[str] = mapped_column(
        String(2000),
        index=True,
        doc="Normalized deduplication URL.",
        comment="Normalized deduplication URL.",
    )
    title: Mapped[str] = mapped_column(
        Text, doc="Plain text title.", comment="Plain text title."
    )
    excerpt: Mapped[str] = mapped_column(
        Text,
        default="",
        doc="Bounded plain text excerpt.",
        comment="Bounded plain text excerpt.",
    )
    content: Mapped[str] = mapped_column(
        Text, default="", doc="Retained cleaned text.", comment="Retained cleaned text."
    )
    content_hash: Mapped[str] = mapped_column(
        String(64),
        doc="Hash of significant source content.",
        comment="Hash of significant source content.",
    )
    metadata_json: Mapped[dict] = mapped_column(
        JSONB, default=dict, doc="Adapter metadata.", comment="Adapter metadata."
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        index=True,
        doc="Source publication time.",
        comment="Source publication time.",
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
        doc="First ingestion time.",
        comment="First ingestion time.",
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        doc="Latest observation time.",
        comment="Latest observation time.",
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        doc="Source update time.",
        comment="Source update time.",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending_analysis",
        doc="Current analysis state.",
        comment="Current analysis state.",
    )
    duplicate_of_id: Mapped[int | None] = mapped_column(
        ForeignKey("news_items.id", ondelete="SET NULL"),
        index=True,
        doc="Earlier cross-source copy.",
        comment="Earlier cross-source copy.",
    )
    latest_analysis_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "news_analyses.id",
            name="fk_news_items_latest_analysis",
            use_alter=True,
            ondelete="SET NULL",
        ),
        index=True,
        doc="Analysis for the current content.",
        comment="Analysis for the current content.",
    )
    latest_decision_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "news_editorial_decisions.id",
            name="fk_news_items_latest_decision",
            use_alter=True,
            ondelete="SET NULL",
        ),
        doc="Latest editorial decision.",
        comment="Latest editorial decision.",
    )
    source: Mapped["NewsSource"] = relationship(lazy="raise_on_sql")
    analysis: Mapped["NewsAnalysis | None"] = relationship(
        foreign_keys=[latest_analysis_id], lazy="raise_on_sql", post_update=True
    )
    decision: Mapped["NewsEditorialDecision | None"] = relationship(
        foreign_keys=[latest_decision_id], lazy="raise_on_sql", post_update=True
    )

    def __repr__(self) -> str:
        return f"<NewsItem(id={self.id}, source_id={self.source_id})>"
