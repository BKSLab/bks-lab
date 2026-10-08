"""Subscriber persistence and read-only paging."""

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Subscriber
from src.exceptions.repositories import SubscriberRepositoryError


class SubscriberRepository:
    def __init__(self, db_session: AsyncSession) -> None:
        self.db_session = db_session

    async def subscribe(self, email: str) -> None:
        """Insert once, preserving the original subscription time on races/retries."""
        try:
            await self.db_session.execute(
                insert(Subscriber).values(email=email).on_conflict_do_nothing(
                    index_elements=[Subscriber.email]
                )
            )
            await self.db_session.commit()
        except (SQLAlchemyError, OSError) as error:
            await self.db_session.rollback()
            raise SubscriberRepositoryError("Subscriber write failed") from error

    async def get_page(self, *, page: int, page_size: int) -> tuple[list[Subscriber], int]:
        """Read newest subscribers first, with deterministic ordering for ties."""
        try:
            total = await self.db_session.scalar(select(func.count()).select_from(Subscriber))
            result = await self.db_session.scalars(
                select(Subscriber)
                .order_by(Subscriber.subscribed_at.desc(), Subscriber.email.asc())
                .offset((page - 1) * page_size).limit(page_size)
            )
            return list(result), int(total or 0)
        except (SQLAlchemyError, OSError) as error:
            await self.db_session.rollback()
            raise SubscriberRepositoryError("Subscriber read failed") from error
