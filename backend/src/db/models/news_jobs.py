"""Durable queue records with expiring ownership and collection run history."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.models.base import Base

if TYPE_CHECKING:
    from src.db.models.news_items import NewsItem
    from src.db.models.news_sources import NewsSource


class NewsJob(Base):
    __tablename__ = "news_jobs"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('collect', 'discover', 'analyze')", name="ck_news_jobs_kind"
        ),
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_news_jobs_status",
        ),
        Index("ix_news_jobs_queue", "status", "kind", "available_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, doc="Job ID.", comment="Job ID.")
    slug: Mapped[str] = mapped_column(
        String(240), unique=True, doc="Stable readable queue address.", comment="Stable readable queue address."
    )
    kind: Mapped[str] = mapped_column(
        String(12), doc="Pipeline stage.", comment="Pipeline stage."
    )
    status: Mapped[str] = mapped_column(
        String(12), default="queued", doc="Queue state.", comment="Queue state."
    )
    source_id: Mapped[int | None] = mapped_column(
        ForeignKey("news_sources.id", ondelete="CASCADE"),
        index=True,
        doc="Optional source scope.",
        comment="Optional source scope.",
    )
    item_id: Mapped[int | None] = mapped_column(
        ForeignKey("news_items.id", ondelete="CASCADE"),
        index=True,
        doc="Optional item scope.",
        comment="Optional item scope.",
    )
    dedupe_key: Mapped[str | None] = mapped_column(
        String(500),
        unique=True,
        doc="Stable scheduler or analysis identity.",
        comment="Stable scheduler or analysis identity.",
    )
    payload: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        doc="Validated work parameters.",
        comment="Validated work parameters.",
    )
    result: Mapped[dict | None] = mapped_column(
        JSONB, doc="Safe stage result.", comment="Safe stage result."
    )
    progress: Mapped[dict] = mapped_column(
        JSONB, default=dict, doc="Stage counters.", comment="Stage counters."
    )
    error: Mapped[str | None] = mapped_column(
        Text, doc="Safe failure summary.", comment="Safe failure summary."
    )
    attempts: Mapped[int] = mapped_column(
        Integer, default=0, doc="Acquisition count.", comment="Acquisition count."
    )
    owner_token: Mapped[str | None] = mapped_column(
        String(100), doc="Lease ownership token.", comment="Lease ownership token."
    )
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        index=True,
        doc="Lease expiry.",
        comment="Lease expiry.",
    )
    heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        doc="Last valid heartbeat.",
        comment="Last valid heartbeat.",
    )
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        doc="Earliest retry time.",
        comment="Earliest retry time.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
        doc="Enqueue time.",
        comment="Enqueue time.",
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        doc="Latest acquisition time.",
        comment="Latest acquisition time.",
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        doc="Terminal state time.",
        comment="Terminal state time.",
    )
    source: Mapped["NewsSource | None"] = relationship(lazy="raise_on_sql")
    item: Mapped["NewsItem | None"] = relationship(lazy="raise_on_sql")

    def __repr__(self) -> str:
        return f"<NewsJob(id={self.id}, kind={self.kind}, status={self.status})>"


class NewsSourceRun(Base):
    __tablename__ = "news_source_runs"

    id: Mapped[int] = mapped_column(primary_key=True, doc="Run ID.", comment="Run ID.")
    source_id: Mapped[int] = mapped_column(
        ForeignKey("news_sources.id", ondelete="CASCADE"),
        index=True,
        doc="Collected source.",
        comment="Collected source.",
    )
    job_id: Mapped[int | None] = mapped_column(
        ForeignKey("news_jobs.id", ondelete="SET NULL"),
        index=True,
        doc="Owning collection job.",
        comment="Owning collection job.",
    )
    source_name: Mapped[str] = mapped_column(
        String(200), doc="Source name at start.", comment="Source name at start."
    )
    source_slug: Mapped[str] = mapped_column(
        String(160), index=True, doc="Source address at start.", comment="Source address at start."
    )
    source_url: Mapped[str] = mapped_column(
        Text, doc="Source URL at start.", comment="Source URL at start."
    )
    source_kind: Mapped[str] = mapped_column(
        String(10), doc="Adapter at start.", comment="Adapter at start."
    )
    parameters: Mapped[dict] = mapped_column(
        JSONB, default=dict, doc="Safe collection parameters.", comment="Safe collection parameters."
    )
    not_modified: Mapped[bool] = mapped_column(
        Boolean, default=False, doc="Conditional request returned no changes.", comment="Conditional request returned no changes."
    )
    http_status: Mapped[int | None] = mapped_column(
        Integer, doc="Final source HTTP status.", comment="Final source HTTP status."
    )
    limit_reached: Mapped[bool] = mapped_column(
        Boolean, default=False, doc="Collection candidate limit reached.", comment="Collection candidate limit reached."
    )
    diagnostics_truncated: Mapped[bool] = mapped_column(
        Boolean, default=False, doc="Detailed observation limit reached.", comment="Detailed observation limit reached."
    )
    status: Mapped[str] = mapped_column(
        String(20), default="running", doc="Run state.", comment="Run state."
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
        doc="Start time.",
        comment="Start time.",
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), doc="Completion time.", comment="Completion time."
    )
    new_count: Mapped[int] = mapped_column(
        Integer, default=0, doc="Inserted materials.", comment="Inserted materials."
    )
    updated_count: Mapped[int] = mapped_column(
        Integer, default=0, doc="Changed materials.", comment="Changed materials."
    )
    unchanged_count: Mapped[int] = mapped_column(
        Integer, default=0, doc="Unchanged materials.", comment="Unchanged materials."
    )
    skipped_count: Mapped[int] = mapped_column(
        Integer, default=0, doc="Skipped candidates.", comment="Skipped candidates."
    )
    warning_count: Mapped[int] = mapped_column(
        Integer, default=0, doc="Candidates with collection warnings.", comment="Candidates with collection warnings."
    )
    error: Mapped[str | None] = mapped_column(
        Text, doc="Safe failure summary.", comment="Safe failure summary."
    )
    source: Mapped["NewsSource"] = relationship(lazy="raise_on_sql")
    job: Mapped[NewsJob | None] = relationship(lazy="raise_on_sql")

    def __repr__(self) -> str:
        return f"<NewsSourceRun(id={self.id}, source_id={self.source_id})>"
