"""Expiry cleanup preserves valid sessions and never renews expired rows."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from src.db.models import AdminSession
from src.repositories.admin_sessions import AdminSessionRepository


async def test_expiry_cleanup_and_renewal_boundary(db_session):
    now = datetime(2026, 2, 20, 12, tzinfo=timezone.utc)
    db_session.add_all([
        AdminSession(token_hash="expired", username="admin", expires_at=now-timedelta(seconds=1)),
        AdminSession(token_hash="boundary", username="admin", expires_at=now),
        AdminSession(token_hash="valid", username="admin", expires_at=now+timedelta(seconds=1)),
    ])
    await db_session.commit()
    repository = AdminSessionRepository(db_session)
    assert not await repository.renew(token_hash="boundary", username="admin", now=now, expires_at=now+timedelta(hours=12))
    assert not await repository.renew(token_hash="valid", username="other", now=now, expires_at=now+timedelta(hours=12))
    await repository.delete_expired(now)
    assert [row.token_hash for row in await db_session.scalars(select(AdminSession))] == ["valid"]
    await repository.delete_expired(now)
    assert await repository.renew(token_hash="valid", username="admin", now=now, expires_at=now+timedelta(hours=12))
    assert await repository.renew(token_hash="valid", username="admin", now=now, expires_at=now+timedelta(hours=11))
    await db_session.refresh(await db_session.get(AdminSession, "valid"))
    assert (await db_session.get(AdminSession, "valid")).expires_at == now+timedelta(hours=12)
