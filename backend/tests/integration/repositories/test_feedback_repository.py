"""Feedback write failures roll back the real PostgreSQL transaction."""

import pytest
from sqlalchemy import select

from src.db.models import FeedbackMessage
from src.exceptions.repositories import FeedbackRepositoryError
from src.repositories.feedback import FeedbackRepository


async def test_failed_feedback_write_rolls_back_before_the_next_message(db_session):
    repository = FeedbackRepository(db_session)
    with pytest.raises(FeedbackRepositoryError):
        await repository.create(name=None, email="visitor@example.com", message="Private test message")

    await repository.create(name="Visitor", email="visitor@example.com", message="A valid test message")
    rows = list(await db_session.scalars(select(FeedbackMessage)))
    assert len(rows) == 1
    assert rows[0].message == "A valid test message"
