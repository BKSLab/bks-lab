"""One-time import of Markdown content files into the PostgreSQL storage.

Run manually inside the backend container:

    python -m scripts.import_content_to_db

For every valid file under ``content/{articles,notes,projects}/`` the script
upserts one ``content_items`` row keyed by (type, slug) — existing rows keep
their id, which visit statistics reference — and appends a revision snapshot.
Re-running without file changes is a no-op: no row writes, no new revisions.
Invalid files are skipped and listed in the stdout report.

Field derivation lives in src/services/content_fields.py and is shared with
the admin save path.
"""

import asyncio
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from stat import S_ISREG
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.core.settings import get_settings
from src.db.session import async_session_factory, engine
from src.repositories.content_items import ContentItemRepository
from src.repositories.content_revisions import ContentRevisionRepository
from src.schemas.frontmatter import ArticleFrontmatter, NoteFrontmatter, ProjectFrontmatter
from src.services.content_fields import (
    ContentFields,
    build_item_values,
    build_snapshot,
    resolve_status,
)
from src.utils import markdown as md

logger = logging.getLogger(__name__)

CONTENT_TYPES: dict[str, tuple[str, type[BaseModel]]] = {
    "article": ("articles", ArticleFrontmatter),
    "note": ("notes", NoteFrontmatter),
    "project": ("projects", ProjectFrontmatter),
}

Frontmatter = ArticleFrontmatter | NoteFrontmatter | ProjectFrontmatter


@dataclass
class ImportReport:
    """Counters and per-file errors of one import run."""

    created: int = 0
    updated: int = 0
    unchanged: int = 0
    errors: list[str] = field(default_factory=list)


def frontmatter_fields(frontmatter: Frontmatter, body: str) -> ContentFields:
    """Normalize a validated frontmatter plus body into editable fields."""
    return ContentFields(
        title=frontmatter.title,
        status=resolve_status(
            draft=frontmatter.draft, lifecycle=getattr(frontmatter, "status", None)
        ),
        content_markdown=body,
        category=getattr(frontmatter, "category", None),
        tags=list(getattr(frontmatter, "tags", []) or []),
        published_at=getattr(frontmatter, "published_at", None),
        excerpt=getattr(frontmatter, "excerpt", None),
        cover_image=getattr(frontmatter, "cover_image", None),
        seo_title=getattr(frontmatter, "seo_title", None),
        seo_description=getattr(frontmatter, "seo_description", None),
        og_image=getattr(frontmatter, "og_image", None),
        related_slug=getattr(frontmatter, "related", None),
        featured=getattr(frontmatter, "featured", False),
        sort_order=getattr(frontmatter, "order", None),
        reading_time_override=getattr(frontmatter, "reading_time", None),
    )


def _values_equal(row: Any, values: dict[str, Any]) -> bool:
    """Compare every imported column against the stored row."""
    return all(getattr(row, key) == value for key, value in values.items())


def _parse_file(content_type: str, model: type[BaseModel], path: Path) -> tuple[Frontmatter, str]:
    """Parse and validate one file; raises ValueError subclasses on failure."""
    slug = path.stem
    if not md.is_valid_slug(slug):
        raise ValueError(f"invalid slug {slug!r}")
    data, body = md.parse_frontmatter(path.read_text(encoding="utf-8"))
    return model.model_validate(data), body


def _content_files(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(
        path for path in directory.iterdir()
        if path.suffix == ".md" and S_ISREG(path.stat().st_mode)
    )


async def _import_file(
    session_factory: async_sessionmaker[AsyncSession],
    content_type: str,
    path: Path,
    values: dict[str, Any],
    report: ImportReport,
) -> None:
    """Upsert one file and append a revision when its content changed."""
    async with session_factory() as session:
        items = ContentItemRepository(session)
        revisions = ContentRevisionRepository(session)
        existing = await items.get_by_slug(content_type, values["slug"])
        snapshot = build_snapshot(values)
        if existing is None:
            item = await items.create(values)
            await revisions.create(
                item_id=item.id, snapshot=snapshot, word_count=values["word_count"]
            )
            report.created += 1
            logger.info("Imported %s %s", content_type, values["slug"])
        elif _values_equal(existing, values):
            report.unchanged += 1
        else:
            await items.update(existing, values)
            await revisions.create(
                item_id=existing.id, snapshot=snapshot, word_count=values["word_count"]
            )
            report.updated += 1
            logger.info("Updated %s %s", content_type, values["slug"])


async def import_content(
    session_factory: async_sessionmaker[AsyncSession],
    content_root: Path,
    words_per_minute: int,
) -> ImportReport:
    """Import every valid Markdown file under the content root.

    Args:
        session_factory: Async session factory of the target database.
        content_root: Directory containing articles/notes/projects subdirs.
        words_per_minute: Reading speed used to derive reading_time.

    Returns:
        ImportReport with created/updated/unchanged counters and per-file errors.
    """
    report = ImportReport()
    for content_type, (subdirectory, model) in CONTENT_TYPES.items():
        for path in _content_files(content_root / subdirectory):
            try:
                frontmatter, body = _parse_file(content_type, model, path)
                fields = frontmatter_fields(frontmatter, body)
                values = build_item_values(content_type, path.stem, fields, words_per_minute)
            except (ValueError, md.MarkdownParseError, ValidationError, UnicodeDecodeError, OSError) as error:
                logger.error("Skipping invalid %s file %s: %s", content_type, path.name, error)
                report.errors.append(f"{path.name}: {error}")
                continue
            await _import_file(session_factory, content_type, path, values, report)
    return report


async def main() -> int:
    """Import content from the configured directory and print the report."""
    settings = get_settings()
    report = await import_content(
        async_session_factory, settings.content.dir, settings.content.words_per_minute
    )
    await engine.dispose()
    print(
        "Import finished: "
        f"{report.created} imported, {report.updated} updated, "
        f"{report.unchanged} unchanged, {len(report.errors)} errors"
    )
    for error in report.errors:
        print(f"ERROR: {error}")
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
