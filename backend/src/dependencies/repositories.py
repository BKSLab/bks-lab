"""Level 1 dependencies: repository factories.

Markdown content repositories are process-wide singletons (they hold the
in-memory content cache); SQL repositories are per-request.
"""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from src.core.settings import get_settings
from src.db.session import async_session_factory
from src.dependencies.db_session import DbSessionDep
from src.repositories.content_items import ContentItemRepository
from src.repositories.admin_sessions import AdminSessionRepository
from src.repositories.subscribers import SubscriberRepository
from src.repositories.markdown_content import MarkdownContentRepository
from src.repositories.stats import StatsRepository
from src.schemas.frontmatter import ArticleFrontmatter, NoteFrontmatter, ProjectFrontmatter


def _build_markdown_repository(content_type: str, model: type) -> MarkdownContentRepository:
    settings = get_settings()
    return MarkdownContentRepository(
        content_dir=settings.content.dir / f"{content_type}s",
        content_type=content_type,
        frontmatter_model=model,
        session_factory=async_session_factory,
        ttl_seconds=settings.content.sync_ttl_seconds,
        words_per_minute=settings.content.words_per_minute,
    )


@lru_cache
def get_articles_repository() -> MarkdownContentRepository:
    """Singleton repository over content/articles."""
    return _build_markdown_repository("article", ArticleFrontmatter)


@lru_cache
def get_notes_repository() -> MarkdownContentRepository:
    """Singleton repository over content/notes."""
    return _build_markdown_repository("note", NoteFrontmatter)


@lru_cache
def get_projects_repository() -> MarkdownContentRepository:
    """Singleton repository over content/projects."""
    return _build_markdown_repository("project", ProjectFrontmatter)


def get_stats_repository(session: DbSessionDep) -> StatsRepository:
    """Per-request stats repository."""
    return StatsRepository(session)


def get_content_item_repository(session: DbSessionDep) -> ContentItemRepository:
    """Per-request content projection repository."""
    return ContentItemRepository(session)


ArticlesRepositoryDep = Annotated[
    MarkdownContentRepository, Depends(get_articles_repository)
]
NotesRepositoryDep = Annotated[MarkdownContentRepository, Depends(get_notes_repository)]
ProjectsRepositoryDep = Annotated[
    MarkdownContentRepository, Depends(get_projects_repository)
]
StatsRepositoryDep = Annotated[StatsRepository, Depends(get_stats_repository)]
ContentItemRepositoryDep = Annotated[
    ContentItemRepository, Depends(get_content_item_repository)
]


def get_admin_session_repository(session: DbSessionDep) -> AdminSessionRepository:
    """Per-request session repository."""
    return AdminSessionRepository(session)


def get_subscriber_repository(session: DbSessionDep) -> SubscriberRepository:
    """Per-request subscriber repository."""
    return SubscriberRepository(session)


AdminSessionRepositoryDep = Annotated[AdminSessionRepository, Depends(get_admin_session_repository)]
SubscriberRepositoryDep = Annotated[SubscriberRepository, Depends(get_subscriber_repository)]
