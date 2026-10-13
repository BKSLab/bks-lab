"""Store genuine visitor messages and expose them only through the admin API."""

from src.exceptions.feedback import FeedbackUnavailableError
from src.exceptions.repositories import FeedbackRepositoryError
from src.repositories.feedback import FeedbackRepository
from src.schemas.admin import FeedbackRow
from src.schemas.forms import FeedbackRequest
from src.schemas.pagination import Paged


class FeedbackService:
    def __init__(self, repository: FeedbackRepository) -> None:
        self.repository = repository

    async def submit(self, data: FeedbackRequest) -> None:
        """Ignore honeypots and confirm genuine messages only after persistence."""
        if data.website:
            return
        try:
            await self.repository.create(
                name=data.name, email=data.email, message=data.message
            )
        except FeedbackRepositoryError as error:
            raise FeedbackUnavailableError from error

    async def get_page(self, *, page: int, page_size: int) -> Paged[FeedbackRow]:
        """Return a page of received messages for the authenticated owner."""
        rows, total = await self.repository.get_page(page=page, page_size=page_size)
        return Paged[FeedbackRow].build(
            [FeedbackRow.model_validate(row) for row in rows], total, page, page_size
        )
