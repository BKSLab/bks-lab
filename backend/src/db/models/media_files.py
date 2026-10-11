"""ORM model for uploaded images (media_files table).

Files live on the `uploads` volume under /uploads/<section>/<name>.webp;
the table keeps the public path and the metadata needed by the editor's
insert dialog. Rows are created only after the file is written and
validated (see services/media.py).
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.db.models.base import Base


class MediaFile(Base):
    """One uploaded image served from /uploads/."""

    __tablename__ = "media_files"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        comment="Unique identifier of the uploaded file.",
    )
    path: Mapped[str] = mapped_column(
        String(length=500),
        unique=True,
        nullable=False,
        comment="Public path: /uploads/<section>/<file>.webp.",
    )
    original_name: Mapped[str] = mapped_column(
        String(length=255),
        nullable=False,
        comment="Original client-side file name.",
    )
    mime: Mapped[str] = mapped_column(
        String(length=50),
        nullable=False,
        comment="Stored MIME type (image/webp after conversion).",
    )
    size_bytes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Stored file size in bytes.",
    )
    width: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Pixel width after conversion.",
    )
    height: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Pixel height after conversion.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="When the file was uploaded.",
    )

    def __repr__(self) -> str:
        return f"<MediaFile(id={self.id}, path='{self.path}')>"
