"""Project API schemas (see docs/api_contract.md)."""

from typing import Literal

from pydantic import BaseModel, Field

from src.schemas.articles import SeoMeta

ProjectStatus = Literal["active", "archived"]


class ProjectSummary(BaseModel):
    """Project card data for lists."""

    slug: str = Field(..., description="URL slug of the project.", examples=["work-for-everyone"])
    title: str = Field(..., description="Project title.", examples=["Работа для всех"])
    excerpt: str = Field(..., description="Short project description.")
    cover_image: str = Field(..., description="Cover image path.", examples=["/images/projects/work-for-everyone.webp"])
    tags: list[str] = Field(..., description="Technology tags.", examples=[["FastAPI", "Next.js"]])
    status: ProjectStatus = Field(..., description="Lifecycle status.", examples=["active"])
    featured: bool = Field(..., description="Shown on the home page when true.")
    order: int = Field(..., description="Explicit ordering of featured projects.", examples=[1])


class ProjectDetail(ProjectSummary):
    """Full project payload for the project page."""

    content_html: str = Field(..., description="Project description rendered to safe HTML (no raw HTML).")
    seo: SeoMeta = Field(..., description="SEO metadata for the project page.")
