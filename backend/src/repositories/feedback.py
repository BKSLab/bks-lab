"""Feedback persistence and read-only paging."""

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import FeedbackMessage
from src.exceptions.repositories import FeedbackRepositoryError


class FeedbackRepository:
    def __init__(self, db_session: AsyncSession) -> None:
        self.db_session = db_session

    async def create(self, *, name: str, email: str, message: str) -> None:
        """Commit a message before confirming receipt to the visitor."""
        try:
            self.db_session.add(FeedbackMessage(name=name, email=email, message=message))
            await self.db_session.commit()
        except (SQLAlchemyError, OSError) as error:
            await self.db_session.rollback()
            raise FeedbackRepositoryError("Feedback write failed") from error

    async def get_page(self, *, page: int, page_size: int) -> tuple[list[FeedbackMessage], int]:
        """Read newest messages first, with deterministic ordering for ties."""
        try:
            total = await self.db_session.scalar(select(func.count()).select_from(FeedbackMessage))
            result = await self.db_session.scalars(
                select(FeedbackMessage)
                .order_by(FeedbackMessage.created_at.desc(), FeedbackMessage.id.desc())
                .offset((page - 1) * page_size).limit(page_size)
            )
            return list(result), int(total or 0)
        except (SQLAlchemyError, OSError) as error:
            await self.db_session.rollback()
            raise FeedbackRepositoryError("Feedback read failed") from error
