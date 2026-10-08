"""Level 2 dependencies: service factories and injectable clocks."""

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends

from src.core.settings import get_settings
from src.db.session import async_session_factory
from src.dependencies.repositories import (
    AdminSessionRepositoryDep,
    ArticlesRepositoryDep,
    ContentItemRepositoryDep,
    NotesRepositoryDep,
    ProjectsRepositoryDep,
    StatsRepositoryDep,
    SubscriberRepositoryDep,
)
from src.clients.mail import MailClient
from src.services.admin_auth import AdminAuthService
from src.services.admin_content import AdminContentService
from src.services.admin_stats import AdminStatsService
from src.services.articles import ArticleService
from src.services.categories import CategoryService
from src.services.notes import NoteService
from src.services.projects import ProjectService
from src.services.stats import StatsService
from src.services.feedback import FeedbackService
from src.services.subscribers import SubscriberService


def get_utc_now() -> Callable[[], datetime]:
    """Provide the UTC clock as an injectable dependency (testability)."""
    return lambda: datetime.now(timezone.utc)


UtcNowDep = Annotated[Callable[[], datetime], Depends(get_utc_now)]


def get_article_service(
    articles_repository: ArticlesRepositoryDep,
) -> ArticleService:
    """Factory for ArticleService."""
    return ArticleService(articles_repository=articles_repository)


def get_note_service(
    notes_repository: NotesRepositoryDep,
    articles_repository: ArticlesRepositoryDep,
) -> NoteService:
    """Factory for NoteService."""
    return NoteService(
        notes_repository=notes_repository,
        articles_repository=articles_repository,
    )


def get_project_service(
    projects_repository: ProjectsRepositoryDep,
) -> ProjectService:
    """Factory for ProjectService."""
    return ProjectService(projects_repository=projects_repository)


def get_category_service(
    articles_repository: ArticlesRepositoryDep,
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
    articles: ArticlesRepositoryDep, notes: NotesRepositoryDep, projects: ProjectsRepositoryDep,
    utc_now: UtcNowDep,
) -> AdminContentService:
    """Build the content reader with all Markdown projection sources."""
    return AdminContentService(repository=repository, stats=stats, sources=(articles, notes, projects), utc_now=utc_now)


def get_mail_client() -> MailClient:
    """Use only explicitly configured SMTP delivery."""
    return MailClient(get_settings().smtp)


MailClientDep = Annotated[MailClient, Depends(get_mail_client)]


def get_feedback_service(mail_client: MailClientDep) -> FeedbackService:
    """Build the feedback use-case."""
    return FeedbackService(mail_client)


def get_subscriber_service(repository: SubscriberRepositoryDep) -> SubscriberService:
    """Build subscription and subscriber listing use-cases."""
    return SubscriberService(repository)


AdminAuthServiceDep = Annotated[AdminAuthService, Depends(get_admin_auth_service)]
AdminStatsServiceDep = Annotated[AdminStatsService, Depends(get_admin_stats_service)]
AdminContentServiceDep = Annotated[AdminContentService, Depends(get_admin_content_service)]
FeedbackServiceDep = Annotated[FeedbackService, Depends(get_feedback_service)]
SubscriberServiceDep = Annotated[SubscriberService, Depends(get_subscriber_service)]
