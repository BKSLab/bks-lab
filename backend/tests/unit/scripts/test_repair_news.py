"""The repair CLI previews by default and validates scope before queuing work."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from scripts import repair_news as cli
from src.exceptions.news import NewsRepositoryError
from src.repositories.news_items import NewsItemRepository
from src.repositories.news_jobs import NewsJobRepository
from src.repositories.news_sources import NewsSourceRepository


@pytest.fixture
def repositories():
    sources = AsyncMock(spec=NewsSourceRepository)
    sources.get.return_value = SimpleNamespace(id=7, name="private-source-name")
    items = AsyncMock(spec=NewsItemRepository)
    items.ids_for_source.return_value = [3, 1, 2]
    jobs = AsyncMock(spec=NewsJobRepository)
    jobs.enqueue_repair.return_value = [SimpleNamespace(id=41)]
    return sources, items, jobs


def test_parser_requires_source_and_defaults_to_preview():
    with pytest.raises(SystemExit) as error:
        cli.build_parser().parse_args([])
    assert error.value.code == 2
    args = cli.build_parser().parse_args(["--source-id", "7"])
    assert args.source_id == 7 and args.item_id is None and args.apply is False


@pytest.mark.parametrize("option,value", [("--source-id", "0"), ("--source-id", "-1"), ("--item-id", "bad")])
def test_parser_rejects_invalid_ids(option, value):
    with pytest.raises(SystemExit) as error:
        cli.build_parser().parse_args(["--source-id", "7", option, value])
    assert error.value.code == 2


@pytest.mark.asyncio
async def test_dry_run_only_reads_scope_and_counts_batches(repositories):
    sources, items, jobs = repositories
    items.ids_for_source.return_value = list(range(1, 102))

    summary = await cli.repair_news(sources, items, jobs, source_id=7)

    assert summary == {
        "mode": "dry-run", "source_id": 7, "selected_items": 101,
        "planned_batches": 3, "queued_or_active_job_ids": [],
    }
    sources.get.assert_awaited_once_with(7)
    items.ids_for_source.assert_awaited_once_with(7)
    assert jobs.mock_calls == []
    assert "private-source-name" not in json.dumps(summary)


@pytest.mark.asyncio
async def test_apply_passes_sorted_unique_selection_to_atomic_queue(repositories):
    sources, items, jobs = repositories
    args = cli.build_parser().parse_args([
        "--source-id", "7", "--item-id", "3", "--item-id", "1", "--item-id", "3", "--apply",
    ])

    summary = await cli.repair_news(
        sources, items, jobs, source_id=args.source_id, item_ids=args.item_id, apply=args.apply,
    )

    jobs.enqueue_repair.assert_awaited_once_with(7, [1, 3], batch_size=50)
    assert summary == {
        "mode": "apply", "source_id": 7, "selected_items": 2,
        "planned_batches": 1, "queued_or_active_job_ids": [41],
    }
    jobs.enqueue.assert_not_called()


@pytest.mark.asyncio
async def test_unknown_source_is_rejected_without_querying_items_or_writing(repositories):
    sources, items, jobs = repositories
    sources.get.return_value = None
    with pytest.raises(cli.RepairSelectionError, match="Source not found"):
        await cli.repair_news(sources, items, jobs, source_id=7, apply=True)
    assert items.mock_calls == [] and jobs.mock_calls == []


@pytest.mark.asyncio
async def test_foreign_or_missing_item_is_rejected_before_any_write(repositories):
    sources, items, jobs = repositories
    with pytest.raises(cli.RepairSelectionError, match="do not belong"):
        await cli.repair_news(sources, items, jobs, source_id=7, item_ids=[1, 99], apply=True)
    assert jobs.mock_calls == []


@pytest.mark.asyncio
async def test_empty_source_never_queues_a_job(repositories):
    sources, items, jobs = repositories
    items.ids_for_source.return_value = []
    summary = await cli.repair_news(sources, items, jobs, source_id=7, apply=True)
    assert summary["selected_items"] == summary["planned_batches"] == 0
    assert summary["queued_or_active_job_ids"] == []
    assert jobs.mock_calls == []


def test_main_reports_safe_summary(monkeypatch, capsys):
    run = AsyncMock(spec=cli._run, return_value={
        "mode": "dry-run", "source_id": 7, "selected_items": 3,
        "planned_batches": 1, "queued_or_active_job_ids": [],
    })
    monkeypatch.setattr(cli, "_run", run)

    assert cli.main(["--source-id", "7"]) == 0
    assert json.loads(capsys.readouterr().out) == run.return_value
    assert run.call_args.args[0].apply is False


@pytest.mark.parametrize("error", [
    NewsRepositoryError("private-database-connection"),
    SQLAlchemyError("private-engine-configuration"),
    OSError("private-environment-path"),
    ValueError("private-configuration-secret"),
])
def test_main_redacts_storage_and_configuration_failures(monkeypatch, capsys, error):
    monkeypatch.setattr(cli, "_run", AsyncMock(spec=cli._run, side_effect=error))

    assert cli.main(["--source-id", "7", "--apply"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == f"News repair failed ({type(error).__name__})\n"
    assert "private" not in captured.err
