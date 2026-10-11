"""Project use-cases: list (optionally featured) and detail."""

import logging

from src.db.models import ContentItem
from src.exceptions.content import ProjectNotFoundError
from src.repositories.content_items import ContentItemRepository
from src.schemas.articles import DEFAULT_OG_IMAGE, SeoMeta
from src.schemas.projects import ProjectDetail, ProjectSummary
from src.schemas.results import DetailResult
from src.utils import markdown as md

logger = logging.getLogger(__name__)

CONTENT_TYPE = "project"


def build_project_summary(item: ContentItem) -> ProjectSummary:
    """Map a stored project to its public summary schema."""
    return ProjectSummary(
        slug=item.slug,
        title=item.title,
        excerpt=item.excerpt or "",
        cover_image=item.cover_image or "",
        tags=list(item.tags),
        status=item.status,
        featured=item.featured,
        order=item.sort_order or 0,
    )


class ProjectService:
    """Use-cases for portfolio projects."""

    def __init__(self, projects_repository: ContentItemRepository):
        self.projects_repository = projects_repository

    async def list_projects(self, *, featured: bool | None) -> list[ProjectSummary]:
        """Return published projects sorted by order asc, slug asc.

        Args:
            featured: When true, only featured projects (home page);
                when false, only non-featured; when None — all.

        Returns:
            Project summaries; drafts are excluded, archived stay visible.
        """
        items = await self._public_items()
        if featured is not None:
            items = [item for item in items if item.featured is featured]
        return [build_project_summary(item) for item in items]

    async def get_project(self, *, slug: str) -> DetailResult[ProjectDetail]:
        """Return one published project by slug with a content hash for the ETag.

        The hash is derived from the stored HTML, so it changes exactly when
        the rendered content changes.

        Raises:
            ProjectNotFoundError: When the project is missing or is a draft.
        """
        item = await self.projects_repository.get_by_slug(CONTENT_TYPE, slug)
        if item is None or item.status == "draft":
            raise ProjectNotFoundError(slug=slug)
        detail = ProjectDetail(
            **build_project_summary(item).model_dump(),
            content_html=item.content_html or "",
            seo=SeoMeta(
                title=item.seo_title or item.title,
                description=item.seo_description or item.excerpt or "",
                og_image=item.og_image or DEFAULT_OG_IMAGE,
            ),
        )
        return DetailResult(payload=detail, content_hash=md.content_hash(item.content_html or ""))

    async def _public_items(self) -> list[ContentItem]:
        items = await self.projects_repository.list_by_type(
            CONTENT_TYPE, statuses=("active", "archived")
        )
        return sorted(items, key=lambda item: (item.sort_order or 0, item.slug))
