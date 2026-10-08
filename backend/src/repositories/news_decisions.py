"""Append-only editorial decisions with a current pointer on the collected item."""

from sqlalchemy import select

from src.db.models import NewsEditorialDecision, NewsItem
from src.repositories.news_base import NewsRepository


class NewsDecisionRepository(NewsRepository):
    async def create(self, item_id: int, values: dict) -> NewsEditorialDecision | None:
        """Persist the authenticated editor's decision without modifying site content."""
        async with self.operation():
            item = await self.db_session.get(NewsItem, item_id, with_for_update=True)
            if item is None:
                return None
            row = NewsEditorialDecision(item_id=item_id, **values)
            self.db_session.add(row)
            await self.db_session.flush()
            item.latest_decision_id = row.id
            await self.db_session.commit()
            return row

    async def list_for_item(self, item_id: int) -> list[NewsEditorialDecision]:
        """Read editorial history newest first."""
        async with self.operation():
            return list(
                (
                    await self.db_session.scalars(
                        select(NewsEditorialDecision)
                        .where(NewsEditorialDecision.item_id == item_id)
                        .order_by(
                            NewsEditorialDecision.created_at.desc(),
                            NewsEditorialDecision.id.desc(),
                        )
                    )
                ).all()
            )
