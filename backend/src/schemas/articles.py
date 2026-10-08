"""Article API schemas (see docs/api_contract.md)."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

ArticleCategory = Literal["development", "ai", "management", "thoughts", "accessibility"]

DEFAULT_OG_IMAGE = "/og/bks-lab-default.jpg"


class SeoMeta(BaseModel):
    """SEO metadata block of a detail response."""

    title: str = Field(..., description="SEO title.", examples=["Как мы вынесли синхронизации 1С"])
    description: str = Field(..., description="SEO description.", examples=["Аннотация статьи."])
    og_image: str = Field(..., description="Open Graph image path.", examples=[DEFAULT_OG_IMAGE])


class ArticleSummary(BaseModel):
    """Article card data for lists."""

    slug: str = Field(..., description="URL slug of the article.", examples=["1c-async"])
    title: str = Field(..., description="Article title.", examples=["Как мы вынесли синхронизации 1С"])
    excerpt: str = Field(..., description="Short annotation for cards and meta description.")
    category: ArticleCategory = Field(..., description="Category slug.", examples=["development"])
    published_at: date = Field(..., description="Publication date (ISO 8601).", examples=["2026-02-10"])
    reading_time: int = Field(..., ge=1, description="Reading time in minutes.", examples=[8])
    cover_image: str = Field(..., description="Cover image path.", examples=["/images/articles/1c-async.webp"])
    tags: list[str] = Field(..., description="Free-form tags.", examples=[["1C", "async"]])


class ArticleDetail(ArticleSummary):
    """Full article payload for the article page."""

    content_html: str = Field(..., description="Article body rendered to safe HTML (no raw HTML).")
    seo: SeoMeta = Field(..., description="SEO metadata for the article page.")
