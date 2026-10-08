"""Server-side admin sessions; bearer tokens never enter the database."""

from datetime import datetime

from sqlalchemy import DateTime, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.db.models.base import Base


class AdminSession(Base):
    __tablename__ = "admin_sessions"
    __table_args__ = (Index("ix_admin_sessions_expires_at", "expires_at"),)

    token_hash: Mapped[str] = mapped_column(
        String(64), primary_key=True, comment="SHA-256 of the random session token."
    )
    username: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="Configured administrator that owns the session."
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
        comment="When the session was created."
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, comment="Sliding session expiry in UTC."
    )

    def __repr__(self) -> str:
        return f"<AdminSession(expires_at={self.expires_at})>"
