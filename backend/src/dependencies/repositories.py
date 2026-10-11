"""Level 1 dependencies: repository factories.

All repositories are per-request, built on the request-scoped DB session.
"""

from typing import Annotated

from fastapi import Depends

from src.dependencies.db_session import DbSessionDep
from src.repositories.content_items import ContentItemRepository
from src.repositories.content_revisions import ContentRevisionRepository
from src.repositories.media_files import MediaFileRepository
from src.repositories.admin_sessions import AdminSessionRepository
from src.repositories.subscribers import SubscriberRepository
from src.repositories.stats import StatsRepository


def get_stats_repository(session: DbSessionDep) -> StatsRepository:
    """Per-request stats repository."""
    return StatsRepository(session)


def get_content_item_repository(session: DbSessionDep) -> ContentItemRepository:
    """Per-request content storage repository."""
    return ContentItemRepository(session)


def get_content_revision_repository(session: DbSessionDep) -> ContentRevisionRepository:
    """Per-request content revision repository."""
    return ContentRevisionRepository(session)


StatsRepositoryDep = Annotated[StatsRepository, Depends(get_stats_repository)]
ContentItemRepositoryDep = Annotated[
    ContentItemRepository, Depends(get_content_item_repository)
]
ContentRevisionRepositoryDep = Annotated[
    ContentRevisionRepository, Depends(get_content_revision_repository)
]


def get_media_file_repository(session: DbSessionDep) -> MediaFileRepository:
    """Per-request media files repository."""
    return MediaFileRepository(session)


MediaFileRepositoryDep = Annotated[
    MediaFileRepository, Depends(get_media_file_repository)
]


def get_admin_session_repository(session: DbSessionDep) -> AdminSessionRepository:
    """Per-request session repository."""
    return AdminSessionRepository(session)


def get_subscriber_repository(session: DbSessionDep) -> SubscriberRepository:
    """Per-request subscriber repository."""
    return SubscriberRepository(session)


AdminSessionRepositoryDep = Annotated[AdminSessionRepository, Depends(get_admin_session_repository)]
SubscriberRepositoryDep = Annotated[SubscriberRepository, Depends(get_subscriber_repository)]
