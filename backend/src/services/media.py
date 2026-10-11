"""Upload pipeline for editor images: validate, convert to WebP, store.

Files are written under <media dir>/<section>/<slug>-<suffix>.webp and
registered in media_files; the public path is /uploads/<section>/<name>.webp.
Pillow decodes the upload — the declared content type is never trusted.
"""

import logging
import re
import secrets
from io import BytesIO
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from src.core.settings import MediaSettings
from src.db.models import MediaFile
from src.exceptions.admin import MediaFileTooLargeError, MediaValidationError
from src.repositories.media_files import MediaFileRepository

logger = logging.getLogger(__name__)

ALLOWED_SECTIONS = frozenset({"articles", "notes", "projects", "covers", "shared"})
_INPUT_FORMATS = frozenset({"JPEG", "PNG", "WEBP"})
_STORED_MIME = "image/webp"
_WEBP_QUALITY = 85

_SLUG_CHARS = re.compile(r"[^a-z0-9]+")


def _slugify_name(original_name: str) -> str:
    """Derive a safe lowercase ascii stem from the original file name."""
    stem = Path(original_name).stem.lower()
    slug = _SLUG_CHARS.sub("-", stem).strip("-")
    return slug or "image"


def process_image(
    data: bytes, *, max_bytes: int, max_width: int
) -> tuple[bytes, int, int]:
    """Validate and convert an uploaded image to WebP bytes.

    Returns:
        Tuple of (webp bytes, width, height) after optional downscaling.

    Raises:
        MediaFileTooLargeError: When the source exceeds the size limit.
        MediaValidationError: When the payload is not a supported image.
    """
    if len(data) > max_bytes:
        raise MediaFileTooLargeError
    try:
        with Image.open(BytesIO(data)) as image:
            if image.format not in _INPUT_FORMATS:
                raise MediaValidationError
            if image.mode not in ("RGB", "RGBA", "L"):
                image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
            if image.width > max_width:
                height = round(image.height * max_width / image.width)
                image = image.resize((max_width, height), Image.LANCZOS)
            output = BytesIO()
            image.save(output, "WEBP", quality=_WEBP_QUALITY, method=6)
            return output.getvalue(), image.width, image.height
    except (UnidentifiedImageError, OSError, ValueError) as error:
        raise MediaValidationError from error


class MediaService:
    """Use-cases of the editor image library (/api/admin/content/images)."""

    def __init__(self, *, files: MediaFileRepository, settings: MediaSettings) -> None:
        self.files = files
        self.settings = settings

    async def save_upload(
        self, *, original_name: str, data: bytes, section: str = "shared"
    ) -> MediaFile:
        """Convert one upload, write the file and register it in the database.

        The database row is written only after the file is on disk; when the
        insert fails the orphaned file is removed.

        Raises:
            MediaValidationError: On an unknown section or a non-image payload.
            MediaFileTooLargeError: When the source exceeds the size limit.
        """
        if section not in ALLOWED_SECTIONS:
            raise MediaValidationError
        webp, width, height = process_image(
            data, max_bytes=self.settings.max_bytes, max_width=self.settings.max_width
        )
        name = f"{_slugify_name(original_name)}-{secrets.token_hex(4)}.webp"
        relative = f"{section}/{name}"
        target = self.settings.dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(webp)
        try:
            media = await self.files.add({
                "path": f"/uploads/{relative}",
                "original_name": original_name[:255],
                "mime": _STORED_MIME,
                "size_bytes": len(webp),
                "width": width,
                "height": height,
            })
        except Exception:
            target.unlink(missing_ok=True)
            raise
        logger.info("Stored upload %s (%s bytes) as %s", original_name, len(webp), media.path)
        return media

    async def list_images(self) -> list[MediaFile]:
        """List uploaded images, newest first (bounded by the repository)."""
        return await self.files.list_all()
