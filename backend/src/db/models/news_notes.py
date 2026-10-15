"""Durable automatic-note queue and its shared publication clock."""

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, false, func
from sqlalchemy.orm import Mapped, mapped_column

from src.db.models.base import Base


class NewsNoteSetting(Base):
    """One locked row serializes publishers across processes and restarts."""

    __tablename__ = "news_note_settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_news_note_settings_singleton"),
        CheckConstraint("interval_minutes BETWEEN 10 AND 1440", name="ck_news_note_settings_interval"),
        CheckConstraint("max_age_hours BETWEEN 1 AND 720", name="ck_news_note_settings_age"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, doc="Singleton ID.", comment="Singleton ID.")
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), doc="Publication enabled.", comment="Publication enabled.")
    interval_minutes: Mapped[int] = mapped_column(Integer, default=10, server_default="10", doc="Minimum publication interval.", comment="Minimum publication interval.")
    max_age_hours: Mapped[int] = mapped_column(Integer, default=72, server_default="72", doc="Maximum source and waiting age.", comment="Maximum source and waiting age.")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), doc="First activation; immutable on resume.", comment="First activation; immutable on resume.")
    last_published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), doc="Shared durable publication clock.", comment="Shared durable publication clock.")


class NewsNoteQueue(Base):
    """A permanent source identity, surviving raw retention and content deletion."""

    __tablename__ = "news_note_queue"
    __table_args__ = (
        CheckConstraint("status IN ('queued', 'published', 'excluded', 'expired')", name="ck_news_note_queue_status"),
        Index("ix_news_note_queue_status_created", "status", "created_at", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, doc="Queue ID.", comment="Queue ID.")
    note_slug: Mapped[str] = mapped_column(String(200), unique=True, doc="Stable note address.", comment="Stable note address.")
    content_id: Mapped[int | None] = mapped_column(ForeignKey("content_items.id", ondelete="SET NULL"), unique=True, doc="Draft or published content; null after editor deletion.", comment="Draft or published content; null after editor deletion.")
    source_item_id: Mapped[int | None] = mapped_column(ForeignKey("news_items.id", ondelete="SET NULL"), index=True, doc="Collected material, when retained.", comment="Collected material, when retained.")
    analysis_id: Mapped[int | None] = mapped_column(ForeignKey("news_analyses.id", ondelete="SET NULL"), index=True, doc="Original saved analysis, when retained.", comment="Original saved analysis, when retained.")
    source_key: Mapped[str] = mapped_column(String(64), unique=True, doc="Permanent normalized source URL hash.", comment="Permanent normalized source URL hash.")
    external_key: Mapped[str | None] = mapped_column(String(64), unique=True, doc="Permanent profile and external ID hash.", comment="Permanent profile and external ID hash.")
    content_hash: Mapped[str] = mapped_column(String(64), doc="Source version used by this note.", comment="Source version used by this note.")
    title: Mapped[str] = mapped_column(Text, doc="Last queued title snapshot.", comment="Last queued title snapshot.")
    text: Mapped[str] = mapped_column(Text, doc="Last queued text snapshot.", comment="Last queued text snapshot.")
    source_name: Mapped[str] = mapped_column(Text, doc="Server-owned source name snapshot.", comment="Server-owned source name snapshot.")
    source_url: Mapped[str] = mapped_column(Text, doc="Server-owned exact article URL snapshot.", comment="Server-owned exact article URL snapshot.")
    source_published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), doc="Source publication time snapshot.", comment="Source publication time snapshot.")
    source_first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), doc="Original ingestion time snapshot.", comment="Original ingestion time snapshot.")
    status: Mapped[str] = mapped_column(String(20), default="queued", doc="Queue disposition.", comment="Queue disposition.")
    reason: Mapped[str | None] = mapped_column(Text, doc="Terminal disposition explanation.", comment="Terminal disposition explanation.")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), doc="Queue insertion time.", comment="Queue insertion time.")
    published_at_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), doc="Actual note publication time.", comment="Actual note publication time.")
