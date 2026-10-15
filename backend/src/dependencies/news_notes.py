"""Constructor DI for automatic note use cases; shares one request transaction."""

from typing import Annotated

from fastapi import Depends

from src.core.settings import get_settings
from src.dependencies.repositories import ContentItemRepositoryDep, ContentRevisionRepositoryDep, NewsNoteRepositoryDep
from src.dependencies.services import RevalidationClientDep, UtcNowDep
from src.services.news_notes import NewsNoteService


def get_news_note_service(
    repository: NewsNoteRepositoryDep, items: ContentItemRepositoryDep,
    revisions: ContentRevisionRepositoryDep, revalidator: RevalidationClientDep, utc_now: UtcNowDep,
) -> NewsNoteService:
    """Build note administration without provider/scheduler resources."""
    return NewsNoteService(
        repository=repository, items=items, revisions=revisions,
        revalidator=revalidator, words_per_minute=get_settings().content.words_per_minute, utc_now=utc_now,
    )


NewsNoteServiceDep = Annotated[NewsNoteService, Depends(get_news_note_service)]
