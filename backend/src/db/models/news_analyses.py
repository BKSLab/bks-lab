"""Validated model outputs and immutable editorial decisions."""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
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
from src.db.models.news_catalog import NewsCategory, NewsTopic, news_analysis_topics


class NewsAnalysis(Base):
    __tablename__ = "news_analyses"
    __table_args__ = (
        UniqueConstraint(
            "item_id",
            "content_hash",
            "model",
            "prompt_version",
            name="uq_news_analyses_identity",
        ),
        Index(
            "ix_news_analyses_formats", "recommended_formats", postgresql_using="gin"
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True, doc="Analysis ID.", comment="Analysis ID."
    )
    item_id: Mapped[int] = mapped_column(
        ForeignKey("news_items.id", ondelete="CASCADE"),
        index=True,
        doc="Collected item.",
        comment="Collected item.",
    )
    content_hash: Mapped[str] = mapped_column(
        String(64), doc="Analyzed content version.", comment="Analyzed content version."
    )
    model: Mapped[str] = mapped_column(
        String(200), doc="Provider model name.", comment="Provider model name."
    )
    prompt_version: Mapped[str] = mapped_column(
        String(100),
        doc="Editorial prompt version.",
        comment="Editorial prompt version.",
    )
    is_relevant: Mapped[bool] = mapped_column(
        Boolean,
        doc="Model relevance classification.",
        comment="Model relevance classification.",
    )
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("news_categories.id", ondelete="RESTRICT"),
        index=True,
        doc="Existing editorial category.",
        comment="Existing editorial category.",
    )
    suggested_topics: Mapped[list] = mapped_column(
        JSONB,
        default=list,
        doc="Suggestions outside the taxonomy.",
        comment="Suggestions outside the taxonomy.",
    )
    scores: Mapped[dict] = mapped_column(
        JSONB, doc="Validated criterion scores.", comment="Validated criterion scores."
    )
    summary_ru: Mapped[str] = mapped_column(
        Text, doc="Russian summary.", comment="Russian summary."
    )
    editorial_comment_ru: Mapped[str] = mapped_column(
        Text, doc="Editorial explanation.", comment="Editorial explanation."
    )
    recommended_formats: Mapped[list] = mapped_column(
        JSONB,
        doc="Recommended editorial formats.",
        comment="Recommended editorial formats.",
    )
    confidence: Mapped[float] = mapped_column(
        Float, doc="Model confidence.", comment="Model confidence."
    )
    needs_verification: Mapped[bool] = mapped_column(
        Boolean,
        doc="Requires fact verification.",
        comment="Requires fact verification.",
    )
    news_score: Mapped[float] = mapped_column(
        Float,
        index=True,
        doc="Python weighted news score.",
        comment="Python weighted news score.",
    )
    article_score: Mapped[float] = mapped_column(
        Float,
        index=True,
        doc="Python weighted article score.",
        comment="Python weighted article score.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
        doc="Analysis completion time.",
        comment="Analysis completion time.",
    )
    category: Mapped[NewsCategory | None] = relationship(lazy="raise_on_sql")
    topics: Mapped[list[NewsTopic]] = relationship(
        secondary=news_analysis_topics, lazy="raise_on_sql"
    )

    def __repr__(self) -> str:
        return f"<NewsAnalysis(id={self.id}, item_id={self.item_id})>"


class NewsEditorialDecision(Base):
    __tablename__ = "news_editorial_decisions"
    __table_args__ = (
        CheckConstraint(
            "decision IN ('in_work', 'deferred', 'rejected')",
            name="ck_news_decisions_decision",
        ),
        CheckConstraint(
            "format IN ('longread_candidate', 'short_news_candidate')",
            name="ck_news_decisions_format",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True, doc="Decision ID.", comment="Decision ID."
    )
    item_id: Mapped[int] = mapped_column(
        ForeignKey("news_items.id", ondelete="CASCADE"),
        index=True,
        doc="Collected item.",
        comment="Collected item.",
    )
    decision: Mapped[str] = mapped_column(
        String(20),
        index=True,
        doc="Editorial disposition.",
        comment="Editorial disposition.",
    )
    format: Mapped[str] = mapped_column(
        String(30), doc="Editorial destination.", comment="Editorial destination."
    )
    comment: Mapped[str] = mapped_column(
        Text, default="", doc="Editor comment.", comment="Editor comment."
    )
    editor: Mapped[str] = mapped_column(
        String(200),
        doc="Authenticated editor identity.",
        comment="Authenticated editor identity.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
        doc="Decision time.",
        comment="Decision time.",
    )

    def __repr__(self) -> str:
        return f"<NewsEditorialDecision(id={self.id}, item_id={self.item_id})>"
