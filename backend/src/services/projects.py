"""Project use-cases: list (optionally featured) and detail."""

import logging
from typing import cast

from src.exceptions.content import ProjectNotFoundError
from src.repositories.markdown_content import MarkdownContentRepository, ParsedContent
from src.schemas.articles import DEFAULT_OG_IMAGE, SeoMeta
from src.schemas.frontmatter import ProjectFrontmatter
from src.schemas.projects import ProjectDetail, ProjectSummary
from src.schemas.results import DetailResult

logger = logging.getLogger(__name__)


def _fm(item: ParsedContent) -> ProjectFrontmatter:
    return cast(ProjectFrontmatter, item.frontmatter)


def build_project_summary(item: ParsedContent) -> ProjectSummary:
    """Map a parsed project file to its public summary schema."""
    frontmatter = _fm(item)
    return ProjectSummary(
        slug=item.slug,
        title=frontmatter.title,
        excerpt=frontmatter.excerpt,
        cover_image=frontmatter.cover_image,
        tags=frontmatter.tags,
        status=frontmatter.status,
        featured=frontmatter.featured,
        order=frontmatter.order,
    )


class ProjectService:
    """Use-cases for portfolio projects."""

    def __init__(self, projects_repository: MarkdownContentRepository):
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
            items = [item for item in items if _fm(item).featured is featured]
        return [build_project_summary(item) for item in items]

    async def get_project(self, *, slug: str) -> DetailResult[ProjectDetail]:
        """Return one published project by slug with its content hash.

        Raises:
            ProjectNotFoundError: When the project is missing or is a draft.
        """
        item = await self.projects_repository.get_by_slug(slug)
        if item is None or item.status == "draft":
            raise ProjectNotFoundError(slug=slug)
        frontmatter = _fm(item)
        detail = ProjectDetail(
            **build_project_summary(item).model_dump(),
            content_html=item.content_html,
            seo=SeoMeta(
                title=frontmatter.seo_title or frontmatter.title,
                description=frontmatter.seo_description or frontmatter.excerpt,
                og_image=DEFAULT_OG_IMAGE,
            ),
        )
        return DetailResult(payload=detail, content_hash=item.content_hash)

    async def _public_items(self) -> list[ParsedContent]:
        items = await self.projects_repository.get_all()
        published = [item for item in items if item.status != "draft"]
        return sorted(published, key=lambda item: (_fm(item).order, item.slug))
