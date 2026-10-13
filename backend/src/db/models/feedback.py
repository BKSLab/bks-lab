"""Visitor messages retained for the owner to review in the admin panel."""

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from src.db.models.base import Base


class FeedbackMessage(Base):
    __tablename__ = "feedback_messages"
    __table_args__ = (Index("ix_feedback_messages_created_at", "created_at", "id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment="Message ID.")
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="Visitor name.")
    email: Mapped[str] = mapped_column(String(254), nullable=False, comment="Visitor contact address for a manual reply.")
    message: Mapped[str] = mapped_column(Text, nullable=False, comment="Plain-text visitor message.")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
        comment="UTC time the message was received.",
    )

    def __repr__(self) -> str:
        return f"<FeedbackMessage(id={self.id})>"
