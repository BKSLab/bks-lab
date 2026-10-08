"""PostgreSQL aggregate semantics, calendar boundaries and stable pagination."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from src.db.models import PageView
from src.repositories.stats import StatsRepository
from src.services.admin_stats import AdminStatsService

NOW = datetime(2026, 2, 20, 12, tzinfo=timezone.utc)


async def test_utc_period_boundaries_daily_uniques_and_future_exclusion(db_session):
    fixtures = [
        ("2026-01-21T23:59:59+00:00", "/", "outside", None),
        ("2026-01-22T00:00:00+00:00", "/", "a", "first.example"),
        ("2026-02-13T23:59:59+00:00", "/", "a", None),
        ("2026-02-14T00:00:00+00:00", "/", "a", "search.example"),
        ("2026-02-19T23:59:59+00:00", "/", "a", "search.example"),
        ("2026-02-20T00:00:00+00:00", "/", "a", None),
        ("2026-02-20T10:00:00+00:00", "/", "a", "search.example"),
        ("2026-02-20T12:00:00+00:00", "/blog", "b", None),
        ("2026-02-20T12:00:01+00:00", "/", "future", None),
    ]
    db_session.add_all([
        PageView(viewed_at=datetime.fromisoformat(when), path=path, visitor_hash=visitor, referrer_domain=domain)
        for when, path, visitor, domain in fixtures
    ])
    await db_session.commit()
    await db_session.execute(text("SET TIME ZONE 'Pacific/Honolulu'"))
    service = AdminStatsService(repository=StatsRepository(db_session), utc_now=lambda: NOW)
    overview = await service.overview()
    assert overview.views_today == 3
    assert overview.views_7d == 5
    assert overview.views_30d == 7
    assert overview.uniques_today == 2
    assert [(row.path, row.views) for row in overview.top_pages_30d] == [("/", 6), ("/blog", 1)]
    assert [(row.domain, row.views) for row in overview.top_referrers_30d] == [("search.example", 3), ("first.example", 1)]

    series = await service.timeseries(metric="uniques", period="7d")
    assert len(series) == 7
    assert [point.value for point in series] == [1, 0, 0, 0, 0, 1, 2]
    pages = await service.pages(period="7d", page=1, page_size=1)
    assert pages.total == 2 and pages.pages == 2
    assert pages.items[0].path == "/" and pages.items[0].views == 4
    assert pages.items[0].uniques == 3  # The same hash on three UTC days is three daily uniques.
    assert (await service.pages(period="7d", page=2, page_size=1)).items[0].path == "/blog"
    await db_session.execute(text("RESET TIME ZONE"))


async def test_note_groups_and_referrers_are_bounded_with_stable_ties(db_session):
    db_session.add_all([
        PageView(viewed_at=NOW, path="/notes", note_slug=None, visitor_hash="a"),
        PageView(viewed_at=NOW, path="/notes", note_slug="alpha", visitor_hash="a"),
        PageView(viewed_at=NOW, path="/notes", note_slug="beta", visitor_hash="a"),
        *[PageView(viewed_at=NOW, path="/blog", visitor_hash=str(i), referrer_domain=f"domain-{i:02}.example") for i in range(55)],
    ])
    await db_session.commit()
    repository = StatsRepository(db_session)
    rows, total = await repository.get_pages(start=NOW-timedelta(days=1), end=NOW, page=1, page_size=50)
    assert total == 4
    assert [(row["path"], row["note_slug"]) for row in rows] == [("/blog", None), ("/notes", None), ("/notes", "alpha"), ("/notes", "beta")]
    domains = await repository.get_referrers(NOW-timedelta(days=1), NOW)
    assert len(domains) == 50
    assert domains[0]["domain"] == "domain-00.example"
    assert domains[-1]["domain"] == "domain-49.example"
