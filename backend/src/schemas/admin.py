"""Public shape of the protected Admin API."""

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from src.schemas.articles import ArticleCategory
from src.schemas.projects import ProjectStatus
from src.utils.markdown import is_valid_slug

Period = Literal["7d", "30d", "90d"]
Metric = Literal["views", "uniques"]
ContentType = Literal["article", "note", "project"]
ContentStatus = Literal["active", "draft", "archived"]


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=200)
    password: SecretStr = Field(min_length=1, max_length=1000)


class LoginResponse(BaseModel):
    status: Literal["ok"] = "ok"


class AdminIdentity(BaseModel):
    username: str


class TimeseriesPoint(BaseModel):
    date: date
    value: int


class TopPage(BaseModel):
    path: str
    views: int


class ReferrerRow(BaseModel):
    domain: str
    views: int


class Overview(BaseModel):
    views_today: int
    views_7d: int
    views_30d: int
    uniques_today: int
    top_pages_30d: list[TopPage]
    top_referrers_30d: list[ReferrerRow]


class PageStatsRow(BaseModel):
    path: str
    note_slug: str | None
    views: int
    uniques: int


class ContentItemRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: ContentType
    slug: str
    title: str
    category: str | None
    tags: list[str]
    published_at: date | None
    status: ContentStatus
    word_count: int
    views_30d: int = 0


class ContentItemFull(ContentItemRow):
    """Editor-facing detail: the stored source Markdown and timestamps."""

    content_markdown: str | None
    featured: bool
    sort_order: int | None
    created_at: datetime
    updated_at: datetime


class ContentItemDetail(ContentItemFull):
    """Detail view of the admin showcase; keeps the transitional field names
    `synced_at` (= updated_at) and `content_hash` (= hash of content_html)
    used by the current frontend."""

    synced_at: datetime
    content_hash: str
    views_timeseries_30d: list[TimeseriesPoint]


class _ContentCreateBase(BaseModel):
    """Editable fields shared by all content types on creation."""

    model_config = ConfigDict(extra="forbid")

    slug: str
    title: str = Field(min_length=1, max_length=500)
    tags: list[str] = Field(default_factory=list)
    # New materials are drafts unless the payload explicitly publishes them.
    draft: bool = True
    seo_title: str | None = None
    seo_description: str | None = None
    content_markdown: str = ""

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, value: str) -> str:
        """Apply the shared slug format rules (docs/content_format.md)."""
        if not is_valid_slug(value):
            raise ValueError("Invalid slug format")
        return value


class ArticleCreate(_ContentCreateBase):
    """Create an article; required fields per docs/content_format.md."""

    type: Literal["article"]
    excerpt: str = Field(min_length=1)
    category: ArticleCategory
    published_at: date
    cover_image: str = Field(min_length=1)
    reading_time: int | None = Field(None, ge=1)
    og_image: str | None = None


class NoteCreate(_ContentCreateBase):
    """Create a note; required fields per docs/content_format.md."""

    type: Literal["note"]
    published_at: date
    related_slug: str | None = None


class ProjectCreate(_ContentCreateBase):
    """Create a project; required fields per docs/content_format.md."""

    type: Literal["project"]
    excerpt: str = Field(min_length=1)
    cover_image: str = Field(min_length=1)
    tags: list[str] = Field(min_length=1)
    status: ProjectStatus
    featured: bool
    sort_order: int = Field(ge=0)


ContentCreate = Annotated[
    ArticleCreate | NoteCreate | ProjectCreate, Field(discriminator="type")
]


class ContentPatch(BaseModel):
    """Partial edit of a material; only provided fields change.

    `reading_time` is an override: when omitted it is recomputed from the
    body word count on every save. `status` is the project lifecycle
    (active | archived); the draft flag stays separate.
    """

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(None, min_length=1, max_length=500)
    excerpt: str | None = Field(None, min_length=1)
    category: ArticleCategory | None = None
    published_at: date | None = None
    cover_image: str | None = Field(None, min_length=1)
    tags: list[str] | None = None
    reading_time: int | None = Field(None, ge=1)
    seo_title: str | None = None
    seo_description: str | None = None
    og_image: str | None = None
    related_slug: str | None = None
    featured: bool | None = None
    sort_order: int | None = Field(None, ge=0)
    draft: bool | None = None
    status: ProjectStatus | None = None
    content_markdown: str | None = None


class ContentStatusChange(BaseModel):
    """Explicit status transition; archived is valid for projects only."""

    model_config = ConfigDict(extra="forbid")

    status: ContentStatus


class ContentPreviewRequest(BaseModel):
    """Markdown body to render for the live editor preview."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"content_markdown": "# Заголовок\n\nТекст с [ссылкой](https://bks-lab.ru)."}},
    )

    content_markdown: str = Field(
        min_length=1,
        max_length=100_000,
        description="Markdown body; rendered with the same pipeline used on save.",
        examples=["# Заголовок\n\nТекст."],
    )


class ContentPreviewResponse(BaseModel):
    """Rendered HTML for the live editor preview; sanitization happens on the frontend."""

    html: str = Field(
        ...,
        description="HTML rendered from the submitted Markdown (unsanitized, same as stored content_html).",
        examples=["<h1>Заголовок</h1>\n<p>Текст.</p>\n"],
    )


class ContentRevisionRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    revision_no: int
    word_count: int
    created_at: datetime


class ContentRevisionDetail(ContentRevisionRow):
    snapshot: dict


class MediaFileRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    path: str
    original_name: str
    mime: str
    size_bytes: int
    width: int | None
    height: int | None
    created_at: datetime


class SubscriberRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    email: str
    subscribed_at: datetime


class FeedbackRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Message ID.", examples=[1])
    name: str = Field(description="Visitor name.", examples=["Visitor"])
    email: str = Field(description="Contact address for a manual reply.", examples=["visitor@example.com"])
    message: str = Field(description="Plain-text message.", examples=["I would like to discuss a project."])
    created_at: datetime = Field(description="UTC receipt time.", examples=["2026-10-13T12:00:00Z"])
