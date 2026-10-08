"""ORM model for the page view event log.

Privacy rule: IP addresses and User-Agent strings are never stored;
only the HMAC-derived daily visitor hash is kept.
"""

from datetime import datetime

from sqlalchemy import DateTime, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.db.models.base import Base


class PageView(Base):
    """Single page view event (immutable log row)."""

    __tablename__ = "page_views"

    __table_args__ = (
        Index("ix_page_views_viewed_at", "viewed_at"),
        Index("ix_page_views_path_viewed_at", "path", "viewed_at"),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        comment="Unique identifier of the page view row.",
    )
    viewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="When the view happened (server time, UTC).",
    )
    path: Mapped[str] = mapped_column(
        String(length=500),
        nullable=False,
        comment="Normalized site path without query string and anchor.",
    )
    note_slug: Mapped[str | None] = mapped_column(
        String(length=200),
        nullable=True,
        comment="Slug extracted from a #note-<slug> anchor on the /notes feed.",
    )
    referrer_domain: Mapped[str | None] = mapped_column(
        String(length=255),
        nullable=True,
        comment="Referrer domain only (no path/query); null when absent or invalid.",
    )
    visitor_hash: Mapped[str] = mapped_column(
        String(length=64),
        nullable=False,
        comment="sha256(daily_salt + ip + user_agent); daily salt = HMAC(stats_secret, UTC date).",
    )

    def __repr__(self) -> str:
        return f"<PageView(id={self.id}, path='{self.path}', viewed_at={self.viewed_at})>"
