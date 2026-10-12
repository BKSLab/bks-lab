"""Research suggestions kept separately from verified collection sources."""

from typing import Any

from sqlalchemy import Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.db.models.base import Base


class NewsSourceCatalogueEntry(Base):
    __tablename__ = "news_source_catalogue"

    id: Mapped[str] = mapped_column(
        String(100), primary_key=True,
        doc="Stable research entry ID.", comment="Stable research entry ID.",
    )
    position: Mapped[int] = mapped_column(
        Integer, index=True,
        doc="Display order in the research catalogue.",
        comment="Display order in the research catalogue.",
    )
    data: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        doc="Suggestion metadata, URLs and connection notes; not a verified source.",
        comment="Suggestion metadata, URLs and connection notes; not a verified source.",
    )

    def __repr__(self) -> str:
        return f"<NewsSourceCatalogueEntry(id={self.id})>"
