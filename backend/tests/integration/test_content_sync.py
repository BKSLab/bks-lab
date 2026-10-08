"""Integration tests for the content sync mechanics (architecture section 3).

Covers: TTL + mtime trigger, single-flight rescan, content_hash skip,
atomic upsert+delete, invalid-file exclusion, cache/projection consistency
on database errors.
"""

import asyncio
import os
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from main import app
from src.dependencies.repositories import get_articles_repository
from src.exceptions.repositories import ContentItemRepositoryError, ContentRepositoryError
from src.repositories.content_items import ContentItemRepository
from tests.conftest import make_markdown_repository, write_article


async def projection_slugs(session_factory, content_type: str) -> dict[str, str]:
    async with session_factory() as session:
        rows = await ContentItemRepository(session).get_by_type(content_type)
    return {row.slug: row.status for row in rows}


async def test_initial_scan_populates_cache_and_projection(
    content_dirs: dict[str, Path], session_factory
) -> None:
    repository = make_markdown_repository("article", content_dirs["article"], session_factory)

    items = await repository.get_all()

    # The syntactically invalid file is excluded; drafts stay in the projection.
    assert {item.slug for item in items} == {"article-one", "article-two", "article-draft"}
    projection = await projection_slugs(session_factory, "article")
    assert projection == {
        "article-one": "active",
        "article-two": "active",
        "article-draft": "draft",
    }


async def test_rescan_triggered_by_mtime_change(
    content_dirs: dict[str, Path], session_factory
) -> None:
    repository = make_markdown_repository("article", content_dirs["article"], session_factory)
    await repository.get_all()

    write_article(content_dirs["article"], "article-three", title="Third article")
    items = await repository.get_all()

    assert "article-three" in {item.slug for item in items}
    assert "article-three" in await projection_slugs(session_factory, "article")


async def test_rescan_triggered_by_utime_only(
    content_dirs: dict[str, Path], session_factory
) -> None:
    repository = make_markdown_repository("article", content_dirs["article"], session_factory)
    await repository.get_all()

    target = content_dirs["article"] / "article-one.md"
    target.write_text(
        target.read_text(encoding="utf-8").replace("First article", "Renamed article"),
        encoding="utf-8",
    )
    # Pin mtime into the future so the change cannot fall into the same
    # filesystem timestamp tick as the initial scan.
    future = time.time() + 10
    os.utime(target, (future, future))
    items = await repository.get_all()

    one = next(item for item in items if item.slug == "article-one")
    assert one.frontmatter.title == "Renamed article"


async def test_ttl_prevents_rescan_within_window(
    content_dirs: dict[str, Path], session_factory
) -> None:
    repository = make_markdown_repository("article", content_dirs["article"], session_factory)
    repository._ttl_seconds = 3600.0
    await repository.get_all()

    write_article(content_dirs["article"], "article-three", title="Third article")
    items = await repository.get_all()

    assert "article-three" not in {item.slug for item in items}


async def test_deleted_file_is_removed_from_cache_and_projection(
    content_dirs: dict[str, Path], session_factory
) -> None:
    repository = make_markdown_repository("article", content_dirs["article"], session_factory)
    await repository.get_all()

    (content_dirs["article"] / "article-one.md").unlink()
    items = await repository.get_all()

    assert "article-one" not in {item.slug for item in items}
    assert "article-one" not in await projection_slugs(session_factory, "article")


@pytest.mark.parametrize("invalid_content", [
    "---\nno_title: true\n---\n\nBroken now.\n",
    "---\ntitle: [\n---\n\nBroken YAML.\n",
])
async def test_file_becoming_invalid_is_removed_from_projection(
    content_dirs: dict[str, Path], session_factory, invalid_content
) -> None:
    repository = make_markdown_repository("article", content_dirs["article"], session_factory)
    await repository.get_all()

    target = content_dirs["article"] / "article-one.md"
    target.write_text(invalid_content, encoding="utf-8")
    items = await repository.get_all()

    assert "article-one" not in {item.slug for item in items}
    assert "article-one" not in await projection_slugs(session_factory, "article")
    assert "article-two" in {item.slug for item in items}
    assert "article-two" in await projection_slugs(session_factory, "article")


@pytest.mark.parametrize("warm_cache", [False, True], ids=["cold", "warm"])
@pytest.mark.parametrize("invalid_date", [
    pytest.param("2026-02-30", id="invalid-date"),
    pytest.param("1:" * 180 + "1.0", id="overflowing-float"),
])
async def test_invalid_yaml_constructors_do_not_hide_valid_neighbours(
    client, content_dirs, session_factory, monkeypatch, warm_cache, invalid_date
) -> None:
    now = [100.0]
    monkeypatch.setattr("src.repositories.markdown_content.time", SimpleNamespace(monotonic=lambda: now[0]))
    repository = make_markdown_repository("article", content_dirs["article"], session_factory)
    repository._ttl_seconds = 5.0
    monkeypatch.setitem(app.dependency_overrides, get_articles_repository, lambda: repository)
    if warm_cache:
        initial = await client.get("/api/v1/articles")
        assert initial.status_code == 200
        assert {item["slug"] for item in initial.json()["items"]} == {"article-one", "article-two"}
        assert "article-one" in await projection_slugs(session_factory, "article")

    write_article(content_dirs["article"], "article-one", published_at=invalid_date)
    now[0] += 6.0
    response = await client.get("/api/v1/articles")

    assert response.status_code == 200
    assert {item["slug"] for item in response.json()["items"]} == {"article-two"}
    assert {item.slug for item in await repository.get_all()} == {"article-two", "article-draft"}
    assert set(await projection_slugs(session_factory, "article")) == {"article-two", "article-draft"}
    assert (await client.get("/api/v1/articles/article-one")).status_code == 404
    assert (await client.get("/api/v1/articles/article-two")).status_code == 200

    write_article(content_dirs["article"], "article-one", published_at="2026-02-28")
    now[0] += 6.0
    assert (await client.get("/api/v1/articles/article-one")).status_code == 200
    assert "article-one" in await projection_slugs(session_factory, "article")


@pytest.mark.parametrize("warm_cache", [False, True], ids=["cold", "warm"])
async def test_overlong_filename_does_not_block_valid_content(
    client, content_dirs, session_factory, monkeypatch, warm_cache
) -> None:
    repository = make_markdown_repository("article", content_dirs["article"], session_factory)
    monkeypatch.setitem(app.dependency_overrides, get_articles_repository, lambda: repository)
    valid_slug, invalid_slug = "a" * 200, "b" * 201
    write_article(content_dirs["article"], valid_slug)
    if warm_cache:
        initial = await client.get("/api/v1/articles")
        assert initial.status_code == 200
        assert valid_slug in {item["slug"] for item in initial.json()["items"]}
    write_article(content_dirs["article"], invalid_slug)
    write_article(content_dirs["article"], "after-long-filename")

    response = await client.get("/api/v1/articles")

    assert response.status_code == 200
    expected = {"article-one", "article-two", valid_slug, "after-long-filename"}
    assert {item["slug"] for item in response.json()["items"]} == expected
    assert {item.slug for item in await repository.get_all()} == expected | {"article-draft"}
    assert set(await projection_slugs(session_factory, "article")) == expected | {"article-draft"}
    assert await repository.get_by_slug(invalid_slug) is None


async def test_parallel_requests_trigger_single_rescan(
    content_dirs: dict[str, Path], session_factory
) -> None:
    repository = make_markdown_repository("article", content_dirs["article"], session_factory)
    scan_calls = 0
    original_scan = repository._scan

    def counting_scan():
        nonlocal scan_calls
        scan_calls += 1
        return original_scan()

    repository._scan = counting_scan

    await asyncio.gather(*(repository.ensure_fresh() for _ in range(10)))

    assert scan_calls == 1


async def test_db_error_keeps_previous_cache_and_projection(
    content_dirs: dict[str, Path], session_factory
) -> None:
    repository = make_markdown_repository("article", content_dirs["article"], session_factory)
    await repository.get_all()

    broken_engine = create_async_engine("postgresql+asyncpg://u:p@127.0.0.1:1/none")
    try:
        repository._session_factory = async_sessionmaker(broken_engine)
        write_article(content_dirs["article"], "article-late", title="Late article")

        items = await repository.get_all()

        assert "article-late" not in {item.slug for item in items}
        assert "article-late" not in await projection_slugs(session_factory, "article")
    finally:
        await broken_engine.dispose()


async def test_db_error_on_first_scan_raises(
    content_dirs: dict[str, Path]
) -> None:
    broken_engine = create_async_engine("postgresql+asyncpg://u:p@127.0.0.1:1/none")
    try:
        repository = make_markdown_repository(
            "note", content_dirs["note"], async_sessionmaker(broken_engine)
        )

        with pytest.raises(ContentItemRepositoryError) as exc_info:
            await repository.get_all()

        assert exc_info.value.status_code == 500
    finally:
        await broken_engine.dispose()


async def test_note_projection_has_no_category_and_keeps_reading_time(
    content_dirs: dict[str, Path], session_factory
) -> None:
    repository = make_markdown_repository("note", content_dirs["note"], session_factory)

    await repository.get_all()

    async with session_factory() as session:
        rows = await ContentItemRepository(session).get_by_type("note")
    assert {row.slug for row in rows} == {"note-one", "note-two", "note-broken-link", "note-draft"}
    row = next(row for row in rows if row.slug == "note-one")
    assert row.category is None
    assert row.reading_time is not None and row.reading_time >= 1
    assert row.word_count > 0
    assert row.content_text


async def test_cold_concurrent_reads_wait_for_one_completed_scan(
    content_dirs, session_factory, monkeypatch
) -> None:
    repository = make_markdown_repository("article", content_dirs["article"], session_factory)
    repository._ttl_seconds = 5.0
    started, release = asyncio.Event(), asyncio.Event()
    original_sync = repository._sync_projection
    sync_calls = 0

    async def delayed_sync(items):
        nonlocal sync_calls
        sync_calls += 1
        started.set()
        await release.wait()
        await original_sync(items)

    monkeypatch.setattr(repository, "_sync_projection", delayed_sync)
    reads = [asyncio.create_task(repository.get_all()) for _ in range(5)]
    await started.wait()
    await asyncio.sleep(0)
    try:
        assert not any(read.done() for read in reads)
    finally:
        release.set()
    results = await asyncio.gather(*reads)

    assert sync_calls == 1
    assert all({item.slug for item in items} == {"article-one", "article-two", "article-draft"}
               for items in results)
    assert set(await projection_slugs(session_factory, "article")) == {"article-one", "article-two", "article-draft"}


async def test_failed_cold_scan_is_shared_and_retried_after_ttl(
    content_dirs, session_factory, monkeypatch
) -> None:
    now = [100.0]
    monkeypatch.setattr("src.repositories.markdown_content.time", SimpleNamespace(monotonic=lambda: now[0]))
    repository = make_markdown_repository("article", content_dirs["article"], session_factory)
    repository._ttl_seconds = 5.0
    original_sync = repository._sync_projection
    started, release = asyncio.Event(), asyncio.Event()
    sync_calls = 0
    fail = True

    async def flaky_sync(items):
        nonlocal sync_calls
        sync_calls += 1
        started.set()
        await release.wait()
        if fail:
            raise ContentItemRepositoryError("temporary outage")
        await original_sync(items)

    monkeypatch.setattr(repository, "_sync_projection", flaky_sync)
    reads = [asyncio.create_task(repository.get_all()) for _ in range(5)]
    await started.wait()
    release.set()
    failures = await asyncio.gather(*reads, return_exceptions=True)

    assert all(isinstance(result, ContentItemRepositoryError) for result in failures)
    assert sync_calls == 1
    assert await projection_slugs(session_factory, "article") == {}
    fail = False
    with pytest.raises(ContentItemRepositoryError):
        await repository.get_all()
    assert sync_calls == 1

    now[0] += 6.0
    results = await asyncio.gather(*(repository.get_all() for _ in range(5)))

    assert sync_calls == 2
    assert all(len(items) == 3 for items in results)
    assert len(await projection_slugs(session_factory, "article")) == 3


@pytest.mark.parametrize("warm_cache", [False, True])
@pytest.mark.parametrize("failure", ["missing", "unreadable"])
async def test_unavailable_directory_preserves_cache_and_projection(
    content_dirs, session_factory, monkeypatch, warm_cache, failure
) -> None:
    directory = content_dirs["article"]
    repository = make_markdown_repository("article", directory, session_factory)
    before_items = await repository.get_all() if warm_cache else []
    before_projection = await projection_slugs(session_factory, "article")
    original_iterdir = Path.iterdir

    def unreadable_iterdir(path):
        if path == directory:
            raise PermissionError("temporarily unreadable content directory")
        return original_iterdir(path)

    with monkeypatch.context() as patch:
        if failure == "missing":
            patch.setattr(repository, "_content_dir", directory / "missing")
        else:
            patch.setattr(Path, "iterdir", unreadable_iterdir)
        if warm_cache:
            assert await repository.get_all() == before_items
        else:
            with pytest.raises(ContentRepositoryError):
                await repository.get_all()
        assert await projection_slugs(session_factory, "article") == before_projection

    assert len(await repository.get_all()) == 3
    assert len(await projection_slugs(session_factory, "article")) == 3


async def test_genuinely_empty_directory_removes_projection(content_dirs, session_factory) -> None:
    directory = content_dirs["article"]
    repository = make_markdown_repository("article", directory, session_factory)
    await repository.get_all()
    for path in directory.iterdir():
        path.unlink()

    assert await repository.get_all() == []
    assert await projection_slugs(session_factory, "article") == {}


async def test_edit_to_non_newest_file_refreshes_cache_and_projection(content_dirs, session_factory) -> None:
    directory = content_dirs["article"]
    newest = directory / "article-two.md"
    future = time.time() + 1000
    os.utime(newest, (future, future))
    repository = make_markdown_repository("article", directory, session_factory)
    await repository.get_all()

    changed = write_article(directory, "article-one", title="Changed older file")
    assert changed.stat().st_mtime < newest.stat().st_mtime
    items = await repository.get_all()

    assert next(item for item in items if item.slug == "article-one").frontmatter.title == "Changed older file"
    async with session_factory() as session:
        rows = await ContentItemRepository(session).get_by_type("article")
    assert next(row for row in rows if row.slug == "article-one").title == "Changed older file"


async def test_reading_time_override_reaches_api_and_projection(client, content_dirs, session_factory) -> None:
    write_article(content_dirs["article"], "override", reading_time=17, body="One short paragraph.")

    response = await client.get("/api/v1/articles/override")

    assert response.status_code == 200
    assert response.json()["reading_time"] == 17
    async with session_factory() as session:
        rows = await ContentItemRepository(session).get_by_type("article")
    assert next(row for row in rows if row.slug == "override").reading_time == 17

    write_article(content_dirs["article"], "override", body="One short paragraph.")
    response = await client.get("/api/v1/articles/override")

    assert response.status_code == 200
    assert response.json()["reading_time"] == 1
    async with session_factory() as session:
        rows = await ContentItemRepository(session).get_by_type("article")
    assert next(row for row in rows if row.slug == "override").reading_time == 1
