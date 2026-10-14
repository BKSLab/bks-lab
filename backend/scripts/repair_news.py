"""Preview or enqueue existing-item repairs: python -m scripts.repair_news --help."""

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from src.exceptions.news import NewsRepositoryError
from src.repositories.news_items import NewsItemRepository
from src.repositories.news_jobs import NewsJobRepository
from src.repositories.news_sources import NewsSourceRepository

REPAIR_BATCH_SIZE = 50


class RepairSelectionError(ValueError):
    """A safe operational message for an invalid explicit repair scope."""


def _positive_id(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("Expected a positive integer ID") from None
    if parsed < 1:
        raise argparse.ArgumentTypeError("Expected a positive integer ID")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    """Require a source and keep all database writes behind explicit --apply."""
    parser = argparse.ArgumentParser(description=(
        "Preview existing News Analyzer items for refetch and reanalysis. "
        "Use --apply to queue repairs; the separate scheduler processes them."
    ))
    parser.add_argument("--source-id", type=_positive_id, required=True)
    parser.add_argument(
        "--item-id", type=_positive_id, action="append", default=None,
        help="Limit repair to this item of the source; repeat for several IDs.",
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="Enqueue repair batches of at most 50 items (default: read-only preview).",
    )
    return parser


async def repair_news(
    sources: NewsSourceRepository,
    items: NewsItemRepository,
    jobs: NewsJobRepository,
    *,
    source_id: int,
    item_ids: list[int] | None = None,
    apply: bool = False,
) -> dict[str, Any]:
    """Validate explicit source ownership, then preview or queue bounded repairs."""
    if await sources.get(source_id) is None:
        raise RepairSelectionError("Source not found")
    existing_ids = set(await items.ids_for_source(source_id))
    selected_ids = existing_ids if item_ids is None else set(item_ids)
    if not selected_ids.issubset(existing_ids):
        raise RepairSelectionError("Some requested item IDs do not belong to the selected source")
    selected = sorted(selected_ids)
    summary = {
        "mode": "apply" if apply else "dry-run",
        "source_id": source_id,
        "selected_items": len(selected),
        "planned_batches": (len(selected) + REPAIR_BATCH_SIZE - 1) // REPAIR_BATCH_SIZE,
        "queued_or_active_job_ids": [],
    }
    if apply and selected:
        queued = await jobs.enqueue_repair(source_id, selected, batch_size=REPAIR_BATCH_SIZE)
        summary["queued_or_active_job_ids"] = [job.id for job in queued]
    return summary


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    # Delay settings and engine creation until after parsing, including --help.
    from src.db.session import async_session_factory, engine

    try:
        async with async_session_factory() as session:
            return await repair_news(
                NewsSourceRepository(session), NewsItemRepository(session), NewsJobRepository(session),
                source_id=args.source_id, item_ids=args.item_id, apply=args.apply,
            )
    finally:
        await engine.dispose()


def main(argv: Sequence[str] | None = None) -> int:
    """Print counts and job IDs only, keeping configuration and storage errors private."""
    args = build_parser().parse_args(argv)
    try:
        summary = asyncio.run(_run(args))
    except RepairSelectionError as error:
        print(f"News repair rejected: {error}", file=sys.stderr)
        return 1
    except (NewsRepositoryError, SQLAlchemyError, OSError, ValueError) as error:
        print(f"News repair failed ({type(error).__name__})", file=sys.stderr)
        return 1
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
