"""Immutable per-run observations of collected and skipped candidates."""

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.models.base import Base
from src.db.models.news_jobs import NewsSourceRun


class NewsRunItem(Base):
    __tablename__ = "news_run_items"
    __table_args__ = (
        CheckConstraint(
            "outcome IN ('new', 'updated', 'unchanged', 'skipped')",
            name="ck_news_run_items_outcome",
        ),
        Index("ix_news_run_items_run_outcome", "run_id", "outcome"),
        Index(
            "ix_news_run_items_run_warning", "run_id",
            postgresql_where=text("warning IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True, doc="Observation ID.", comment="Observation ID."
    )
    run_id: Mapped[int] = mapped_column(
        ForeignKey("news_source_runs.id", ondelete="CASCADE"),
        doc="Owning source run.", comment="Owning source run.",
    )
    item_id: Mapped[int | None] = mapped_column(
        ForeignKey("news_items.id", ondelete="SET NULL"), index=True,
        doc="Material if retained.", comment="Material if retained.",
    )
    title: Mapped[str] = mapped_column(
        String(1000), doc="Observed title.", comment="Observed title."
    )
    url: Mapped[str | None] = mapped_column(
        Text, doc="Observed URL.", comment="Observed URL."
    )
    outcome: Mapped[str] = mapped_column(
        String(12), doc="Ingestion outcome.", comment="Ingestion outcome."
    )
    reason: Mapped[str | None] = mapped_column(
        String(500), doc="Safe outcome explanation.", comment="Safe outcome explanation."
    )
    warning: Mapped[str | None] = mapped_column(
        String(500), doc="Safe collection warning.", comment="Safe collection warning."
    )
    stage: Mapped[str | None] = mapped_column(
        String(32), doc="Collection stage.", comment="Collection stage."
    )
    preserved_previous: Mapped[bool] = mapped_column(
        Boolean, default=False,
        doc="Previous sufficient text preserved.", comment="Previous sufficient text preserved.",
    )
    content_hash: Mapped[str | None] = mapped_column(
        String(64), doc="Observed retained version.", comment="Observed retained version."
    )
    run: Mapped[NewsSourceRun] = relationship(lazy="raise_on_sql")

    def __repr__(self) -> str:
        return f"<NewsRunItem(id={self.id}, run_id={self.run_id}, outcome={self.outcome})>"
