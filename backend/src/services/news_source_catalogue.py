"""Expose persisted research suggestions without connecting their URLs."""

from src.repositories.news_source_catalogue import NewsSourceCatalogueRepository
from src.schemas.news_source_catalogue import SourceCatalogueEntry


class NewsSourceCatalogueService:
    def __init__(self, repository: NewsSourceCatalogueRepository) -> None:
        self.repository = repository

    async def list(self) -> list[SourceCatalogueEntry]:
        """Return validated suggestions, using the stored primary ID as authoritative."""
        return [
            SourceCatalogueEntry.model_validate({**row.data, "id": row.id})
            for row in await self.repository.list()
        ]
