"""Level 2 dependencies: service factories and injectable clocks."""

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends

from src.core.settings import get_settings
from src.db.session import async_session_factory
from src.dependencies.repositories import (
    AdminSessionRepositoryDep,
    ContentItemRepositoryDep,
    ContentRevisionRepositoryDep,
    NewsNoteRepositoryDep,
    FeedbackRepositoryDep,
    MediaFileRepositoryDep,
    StatsRepositoryDep,
    SubscriberRepositoryDep,
)
from src.clients.revalidation import RevalidationClient
from src.services.admin_auth import AdminAuthService
from src.services.admin_content import AdminContentService
from src.services.admin_stats import AdminStatsService
from src.services.articles import ArticleService
from src.services.categories import CategoryService
from src.services.content_admin import ContentAdminService
from src.services.notes import NoteService
from src.services.projects import ProjectService
from src.services.stats import StatsService
from src.services.feedback import FeedbackService
from src.services.media import MediaService
from src.services.subscribers import SubscriberService


def get_utc_now() -> Callable[[], datetime]:
    """Provide the UTC clock as an injectable dependency (testability)."""
    return lambda: datetime.now(timezone.utc)


UtcNowDep = Annotated[Callable[[], datetime], Depends(get_utc_now)]


def get_article_service(
    articles_repository: ContentItemRepositoryDep,
) -> ArticleService:
    """Factory for ArticleService."""
    return ArticleService(articles_repository=articles_repository)


def get_note_service(
    notes_repository: ContentItemRepositoryDep,
    articles_repository: ContentItemRepositoryDep,
) -> NoteService:
    """Factory for NoteService."""
    return NoteService(
        notes_repository=notes_repository,
        articles_repository=articles_repository,
    )


def get_project_service(
    projects_repository: ContentItemRepositoryDep,
) -> ProjectService:
    """Factory for ProjectService."""
    return ProjectService(projects_repository=projects_repository)


def get_category_service(
    articles_repository: ContentItemRepositoryDep,
) -> CategoryService:
    """Factory for CategoryService."""
    return CategoryService(articles_repository=articles_repository)


def get_stats_service(utc_now: UtcNowDep) -> StatsService:
    """Factory for StatsService (opens its own sessions for background writes)."""
    settings = get_settings()
    return StatsService(
        session_factory=async_session_factory,
        stats_secret=settings.stats.secret.get_secret_value(),
        utc_now=utc_now,
        referrer_domain_max_length=settings.stats.referrer_domain_max_length,
    )


ArticleServiceDep = Annotated[ArticleService, Depends(get_article_service)]
NoteServiceDep = Annotated[NoteService, Depends(get_note_service)]
ProjectServiceDep = Annotated[ProjectService, Depends(get_project_service)]
CategoryServiceDep = Annotated[CategoryService, Depends(get_category_service)]
StatsServiceDep = Annotated[StatsService, Depends(get_stats_service)]


def get_admin_auth_service(repository: AdminSessionRepositoryDep, utc_now: UtcNowDep) -> AdminAuthService:
    """Build authentication with the request session and an injectable clock."""
    return AdminAuthService(repository=repository, settings=get_settings().admin, utc_now=utc_now)


def get_admin_stats_service(repository: StatsRepositoryDep, utc_now: UtcNowDep) -> AdminStatsService:
    """Build the protected analytics reader."""
    return AdminStatsService(repository=repository, utc_now=utc_now)


def get_admin_content_service(
    repository: ContentItemRepositoryDep, stats: StatsRepositoryDep,
    utc_now: UtcNowDep,
) -> AdminContentService:
    """Build the content reader over the PostgreSQL content storage."""
    return AdminContentService(repository=repository, stats=stats, utc_now=utc_now)


def get_revalidation_client() -> RevalidationClient:
    """Build the best-effort frontend cache revalidation client."""
    return RevalidationClient(get_settings().revalidate)


RevalidationClientDep = Annotated[RevalidationClient, Depends(get_revalidation_client)]


def get_content_admin_service(
    items: ContentItemRepositoryDep,
    revisions: ContentRevisionRepositoryDep,
    revalidator: RevalidationClientDep,
    utc_now: UtcNowDep,
    note_queue: NewsNoteRepositoryDep,
) -> ContentAdminService:
    """Build the content editor write path."""
    return ContentAdminService(
        items=items,
        revisions=revisions,
        revalidator=revalidator,
        words_per_minute=get_settings().content.words_per_minute,
        utc_now=utc_now,
        note_queue=note_queue,
    )


ContentAdminServiceDep = Annotated[ContentAdminService, Depends(get_content_admin_service)]


def get_media_service(files: MediaFileRepositoryDep) -> MediaService:
    """Build the editor image library use-cases."""
    return MediaService(files=files, settings=get_settings().media)


MediaServiceDep = Annotated[MediaService, Depends(get_media_service)]


def get_feedback_service(repository: FeedbackRepositoryDep) -> FeedbackService:
    """Build the feedback use-case."""
    return FeedbackService(repository)


def get_subscriber_service(repository: SubscriberRepositoryDep) -> SubscriberService:
    """Build subscription and subscriber listing use-cases."""
    return SubscriberService(repository)


AdminAuthServiceDep = Annotated[AdminAuthService, Depends(get_admin_auth_service)]
AdminStatsServiceDep = Annotated[AdminStatsService, Depends(get_admin_stats_service)]
AdminContentServiceDep = Annotated[AdminContentService, Depends(get_admin_content_service)]
FeedbackServiceDep = Annotated[FeedbackService, Depends(get_feedback_service)]
SubscriberServiceDep = Annotated[SubscriberService, Depends(get_subscriber_service)]
