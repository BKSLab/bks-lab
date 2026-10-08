"""Idempotent subscriptions and protected subscriber list use-cases."""

from src.repositories.subscribers import SubscriberRepository
from src.schemas.admin import SubscriberRow
from src.schemas.forms import SubscribeRequest
from src.schemas.pagination import Paged


class SubscriberService:
    def __init__(self, repository: SubscriberRepository) -> None:
        self.repository = repository

    async def subscribe(self, data: SubscribeRequest) -> None:
        """Ignore honeypots and register a normalized email without revealing duplicates."""
        if not data.website:
            await self.repository.subscribe(data.email)

    async def get_page(self, *, page: int, page_size: int) -> Paged[SubscriberRow]:
        """Return a page without exposing database internals."""
        rows, total = await self.repository.get_page(page=page, page_size=page_size)
        return Paged[SubscriberRow].build(
            [SubscriberRow.model_validate(row) for row in rows], total, page, page_size
        )
