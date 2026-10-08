"""Pydantic validation schemas for Markdown frontmatter (docs/content_format.md)."""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from src.schemas.articles import ArticleCategory
from src.schemas.projects import ProjectStatus


class _BaseFrontmatter(BaseModel):
    """Common frontmatter fields shared by all content types."""

    model_config = ConfigDict(extra="ignore")

    title: str = Field(..., min_length=1, max_length=500)
    draft: bool = False


class ArticleFrontmatter(_BaseFrontmatter):
    """Frontmatter of an article file (``content/articles/<slug>.md``)."""

    excerpt: str = Field(..., min_length=1)
    category: ArticleCategory
    published_at: date
    cover_image: str = Field(..., min_length=1)
    tags: list[str] = Field(default_factory=list)
    reading_time: int | None = Field(None, ge=1)
    seo_title: str | None = None
    seo_description: str | None = None
    og_image: str | None = None


class NoteFrontmatter(_BaseFrontmatter):
    """Frontmatter of a note file (``content/notes/<slug>.md``)."""

    published_at: date
    tags: list[str] = Field(default_factory=list)
    related: str | None = None


class ProjectFrontmatter(_BaseFrontmatter):
    """Frontmatter of a project file (``content/projects/<slug>.md``)."""

    excerpt: str = Field(..., min_length=1)
    cover_image: str = Field(..., min_length=1)
    tags: list[str] = Field(..., min_length=1)
    status: ProjectStatus
    featured: bool
    order: int = Field(..., ge=0)
    seo_title: str | None = None
    seo_description: str | None = None
