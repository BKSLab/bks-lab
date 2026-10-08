"""Read-only newsletter subscriber registry."""

from datetime import datetime

from sqlalchemy import DateTime, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.db.models.base import Base


class Subscriber(Base):
    __tablename__ = "subscribers"
    __table_args__ = (Index("ix_subscribers_subscribed_at", "subscribed_at"),)

    email: Mapped[str] = mapped_column(
        String(254), primary_key=True, comment="Normalized subscriber email address."
    )
    subscribed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
        comment="UTC time of the first subscription."
    )

    def __repr__(self) -> str:
        return f"<Subscriber(subscribed_at={self.subscribed_at})>"
