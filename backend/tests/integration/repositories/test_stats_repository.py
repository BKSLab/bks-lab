"""Integration tests for StatsRepository on a real database."""

from sqlalchemy import inspect, select

from src.db.models import PageView
from src.repositories.stats import StatsRepository


async def test_save_page_view_persists_row_without_ip_or_user_agent(db_session) -> None:
    repository = StatsRepository(db_session)

    await repository.save_page_view(
        path="/blog/post/1c-async",
        note_slug=None,
        referrer_domain="google.com",
        visitor_hash="ab" * 32,
    )

    rows = (await db_session.execute(select(PageView))).scalars().all()
    assert len(rows) == 1
    row = rows[0]
    assert row.path == "/blog/post/1c-async"
    assert row.note_slug is None
    assert row.referrer_domain == "google.com"
    assert row.visitor_hash == "ab" * 32
    assert row.viewed_at is not None


def test_page_view_model_has_no_ip_or_user_agent_columns() -> None:
    columns = {column.key for column in inspect(PageView).columns}

    assert "ip" not in columns
    assert "user_agent" not in columns
