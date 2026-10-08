"""Editorial taxonomy and explicit source/analysis associations."""

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.models.base import Base


class NewsTopic(Base):
    __tablename__ = "news_topics"

    id: Mapped[int] = mapped_column(
        primary_key=True, doc="Topic ID.", comment="Topic ID."
    )
    name: Mapped[str] = mapped_column(
        String(120), unique=True, doc="Topic name.", comment="Topic name."
    )
    description: Mapped[str] = mapped_column(
        Text, default="", doc="Editorial description.", comment="Editorial description."
    )
    active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        index=True,
        doc="Available for new analysis.",
        comment="Available for new analysis.",
    )

    def __repr__(self) -> str:
        return f"<NewsTopic(id={self.id})>"


class NewsCategory(Base):
    __tablename__ = "news_categories"

    id: Mapped[int] = mapped_column(
        primary_key=True, doc="Category ID.", comment="Category ID."
    )
    name: Mapped[str] = mapped_column(
        String(120), unique=True, doc="Category name.", comment="Category name."
    )
    description: Mapped[str] = mapped_column(
        Text, default="", doc="Editorial description.", comment="Editorial description."
    )
    active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        index=True,
        doc="Available for new analysis.",
        comment="Available for new analysis.",
    )

    def __repr__(self) -> str:
        return f"<NewsCategory(id={self.id})>"


news_source_topics = Table(
    "news_source_topics",
    Base.metadata,
    Column(
        "source_id",
        Integer,
        ForeignKey("news_sources.id", ondelete="CASCADE"),
        primary_key=True,
        doc="Source ID.",
        comment="Source ID.",
    ),
    Column(
        "topic_id",
        Integer,
        ForeignKey("news_topics.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
        doc="Topic ID.",
        comment="Topic ID.",
    ),
)
news_source_categories = Table(
    "news_source_categories",
    Base.metadata,
    Column(
        "source_id",
        Integer,
        ForeignKey("news_sources.id", ondelete="CASCADE"),
        primary_key=True,
        doc="Source ID.",
        comment="Source ID.",
    ),
    Column(
        "category_id",
        Integer,
        ForeignKey("news_categories.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
        doc="Category ID.",
        comment="Category ID.",
    ),
)
news_analysis_topics = Table(
    "news_analysis_topics",
    Base.metadata,
    Column(
        "analysis_id",
        Integer,
        ForeignKey("news_analyses.id", ondelete="CASCADE"),
        primary_key=True,
        doc="Analysis ID.",
        comment="Analysis ID.",
    ),
    Column(
        "topic_id",
        Integer,
        ForeignKey("news_topics.id", ondelete="RESTRICT"),
        primary_key=True,
        index=True,
        doc="Topic ID.",
        comment="Topic ID.",
    ),
)
