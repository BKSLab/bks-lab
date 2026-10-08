"""News source configuration, conditional requests and collection health."""

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.models.base import Base
from src.db.models.news_catalog import (
    NewsCategory,
    NewsTopic,
    news_source_categories,
    news_source_topics,
)


class NewsSource(Base):
    __tablename__ = "news_sources"
    __table_args__ = (
        CheckConstraint("kind IN ('rss', 'html')", name="ck_news_sources_kind"),
        CheckConstraint("priority BETWEEN 0 AND 100", name="ck_news_sources_priority"),
        CheckConstraint("trust_score BETWEEN 0 AND 100", name="ck_news_sources_trust"),
        CheckConstraint("interval_hours >= 1", name="ck_news_sources_interval"),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True, doc="Source ID.", comment="Source ID."
    )
    name: Mapped[str] = mapped_column(
        String(200), doc="Display name.", comment="Display name."
    )
    url: Mapped[str] = mapped_column(
        Text, doc="Checked feed or listing URL.", comment="Checked feed or listing URL."
    )
    kind: Mapped[str] = mapped_column(
        String(10), doc="RSS or HTML adapter.", comment="RSS or HTML adapter."
    )
    config: Mapped[dict] = mapped_column(
        JSONB, default=dict, doc="Adapter selectors.", comment="Adapter selectors."
    )
    active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        index=True,
        doc="Collection enabled.",
        comment="Collection enabled.",
    )
    priority: Mapped[int] = mapped_column(
        Integer, default=50, doc="Collection priority.", comment="Collection priority."
    )
    trust_score: Mapped[int] = mapped_column(
        Integer,
        default=50,
        doc="Editorial source trust.",
        comment="Editorial source trust.",
    )
    vendor_affiliated: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        doc="Commercial affiliation flag.",
        comment="Commercial affiliation flag.",
    )
    interval_hours: Mapped[int] = mapped_column(
        Integer,
        default=6,
        doc="Minimum collection interval.",
        comment="Minimum collection interval.",
    )
    cursor: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        doc="Last committed adapter cursor.",
        comment="Last committed adapter cursor.",
    )
    etag: Mapped[str | None] = mapped_column(
        Text, doc="Last committed ETag.", comment="Last committed ETag."
    )
    last_modified: Mapped[str | None] = mapped_column(
        Text,
        doc="Last committed Last-Modified.",
        comment="Last committed Last-Modified.",
    )
    last_success_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        index=True,
        doc="Last committed successful fetch.",
        comment="Last committed successful fetch.",
    )
    last_error: Mapped[str | None] = mapped_column(
        Text, doc="Safe error summary.", comment="Safe error summary."
    )
    last_new_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        doc="New items in latest fetch.",
        comment="New items in latest fetch.",
    )
    health: Mapped[str] = mapped_column(
        String(20),
        default="unknown",
        doc="Collection health.",
        comment="Collection health.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        doc="Creation time.",
        comment="Creation time.",
    )
    topics: Mapped[list[NewsTopic]] = relationship(
        secondary=news_source_topics, lazy="raise_on_sql"
    )
    categories: Mapped[list[NewsCategory]] = relationship(
        secondary=news_source_categories, lazy="raise_on_sql"
    )

    def __repr__(self) -> str:
        return f"<NewsSource(id={self.id}, kind={self.kind})>"
