"""Singleton editorial settings; no provider credentials or monetary state."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.db.models.base import Base


class NewsSetting(Base):
    __tablename__ = "news_settings"
    __table_args__ = (CheckConstraint("id = 1", name="ck_news_settings_singleton"),)

    id: Mapped[int] = mapped_column(
        primary_key=True, default=1, doc="Singleton key.", comment="Singleton key."
    )
    value: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        doc="Validated editorial configuration.",
        comment="Validated editorial configuration.",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        doc="Last settings change.",
        comment="Last settings change.",
    )

    def __repr__(self) -> str:
        return "<NewsSetting(id=1)>"
