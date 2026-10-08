"""Validated editor requests and safe News Analyzer responses."""

import re
from datetime import datetime
from typing import Annotated, Literal
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

NewsFormat = Literal["longread_candidate", "short_news_candidate"]
NewsDecision = Literal["in_work", "deferred", "rejected"]
NewsStatus = Literal["pending_analysis", "analyzed"]
NewsKind = Literal["rss", "html"]
PositiveID = Annotated[int, Field(ge=1)]


def validate_source_url(value: str) -> str:
    """Reject credentials, fragments and non-web schemes before persisting input."""
    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise ValueError("Use an HTTP(S) URL without credentials or fragment")
    return value


SourceURL = Annotated[
    str, Field(min_length=8, max_length=2000), AfterValidator(validate_source_url)
]


class NewsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class NewsPatch(NewsRequest):
    @model_validator(mode="before")
    @classmethod
    def reject_nulls(cls, value: object) -> object:
        if isinstance(value, dict) and any(item is None for item in value.values()):
            raise ValueError("Omit unchanged fields; null values are not supported")
        return value


class DiscoverRequest(NewsRequest):
    url: SourceURL = Field(
        description="Public feed or listing URL.",
        examples=["https://example.org/feed.xml"],
    )
    kind: NewsKind | None = Field(
        default=None, description="Optional adapter hint.", examples=["rss"]
    )
    config: dict[str, str] = Field(
        default_factory=dict, description="HTML selectors.", examples=[{}]
    )

    @field_validator("config")
    @classmethod
    def validate_config(cls, value: dict[str, str]) -> dict[str, str]:
        keys = {
            "item_selector",
            "title_selector",
            "link_selector",
            "date_selector",
            "content_selector",
        }
        if set(value) - keys or any(
            not selector.strip() or len(selector) > 500 for selector in value.values()
        ):
            raise ValueError("Only nonempty HTML selector fields are supported")
        return {key: selector.strip() for key, selector in value.items()}


class SourceCreate(DiscoverRequest):
    kind: NewsKind = Field(
        description="Successfully discovered source kind.", examples=["rss"]
    )
    name: str = Field(
        min_length=1,
        max_length=200,
        description="Source display name.",
        examples=["Example blog"],
    )
    active: bool = Field(
        default=True, description="Enable scheduled collection.", examples=[True]
    )
    priority: int = Field(
        default=50, ge=0, le=100, description="Editorial priority.", examples=[50]
    )
    trust_score: int = Field(
        default=50, ge=0, le=100, description="Editorial source trust.", examples=[70]
    )
    vendor_affiliated: bool = Field(
        default=False, description="Source has commercial interests.", examples=[False]
    )
    interval_hours: int = Field(
        default=6,
        ge=1,
        le=720,
        description="Minimum interval between fetches.",
        examples=[6],
    )
    topic_ids: list[PositiveID] = Field(
        default_factory=list,
        max_length=50,
        description="Existing topic IDs.",
        examples=[[1]],
    )
    category_ids: list[PositiveID] = Field(
        default_factory=list,
        max_length=50,
        description="Existing category IDs.",
        examples=[[1]],
    )
    discovery_job_id: PositiveID = Field(
        description="Successful matching discovery job.", examples=[1]
    )


class SourcePatch(NewsPatch):
    name: str | None = Field(
        default=None, min_length=1, max_length=200, description="Source display name."
    )
    url: SourceURL | None = Field(default=None, description="Checked replacement URL.")
    kind: NewsKind | None = Field(
        default=None, description="Checked replacement adapter."
    )
    config: dict[str, str] | None = Field(
        default=None, description="Checked replacement selectors."
    )
    active: bool | None = Field(default=None, description="Enable collection.")
    priority: int | None = Field(
        default=None, ge=0, le=100, description="Editorial priority."
    )
    trust_score: int | None = Field(
        default=None, ge=0, le=100, description="Editorial trust."
    )
    vendor_affiliated: bool | None = Field(
        default=None, description="Commercial affiliation."
    )
    interval_hours: int | None = Field(
        default=None, ge=1, le=720, description="Minimum fetch interval."
    )
    topic_ids: list[PositiveID] | None = Field(
        default=None, max_length=50, description="Replacement topic IDs."
    )
    category_ids: list[PositiveID] | None = Field(
        default=None, max_length=50, description="Replacement category IDs."
    )
    discovery_job_id: PositiveID | None = Field(
        default=None, description="Matching discovery required for URL/config changes."
    )

    @field_validator("config")
    @classmethod
    def validate_config(cls, value: dict[str, str] | None) -> dict[str, str] | None:
        return DiscoverRequest.validate_config(value) if value is not None else None


class SourceRow(BaseModel):
    id: int
    name: str
    url: str
    kind: NewsKind
    config: dict[str, str]
    active: bool
    priority: int
    trust_score: int
    vendor_affiliated: bool
    interval_hours: int
    topic_ids: list[int]
    category_ids: list[int]
    last_success_at: datetime | None
    last_error: str | None
    last_new_count: int
    health: str


class CatalogCreate(NewsRequest):
    name: str = Field(
        min_length=1,
        max_length=120,
        description="Editorial label.",
        examples=["AI engineering"],
    )
    description: str = Field(
        default="",
        max_length=3000,
        description="Scope and editorial meaning.",
        examples=["Engineering with language models"],
    )
    active: bool = Field(
        default=True, description="Available for future analysis.", examples=[True]
    )


class CatalogPatch(NewsPatch):
    name: str | None = Field(
        default=None, min_length=1, max_length=120, description="Replacement label."
    )
    description: str | None = Field(
        default=None, max_length=3000, description="Replacement scope."
    )
    active: bool | None = Field(
        default=None, description="Available for future analysis."
    )


class CatalogRow(CatalogCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int = Field(description="Taxonomy ID.", examples=[1])


class ScoreWeights(NewsRequest):
    topical_fit: int = Field(
        ge=0, le=100, description="Topical fit weight.", examples=[40]
    )
    significance: int = Field(
        ge=0, le=100, description="Significance weight.", examples=[25]
    )
    freshness: int = Field(ge=0, le=100, description="Freshness weight.", examples=[25])
    article_potential: int = Field(
        ge=0, le=100, description="Article potential weight.", examples=[10]
    )

    @model_validator(mode="after")
    def require_hundred(self) -> "ScoreWeights":
        if sum(self.model_dump().values()) != 100:
            raise ValueError("Weights must sum to 100")
        return self


class NewsSettingsData(NewsRequest):
    enabled: bool = Field(default=True, description="Enable scheduled collection.")
    timezone: str = Field(
        default="Europe/Samara", max_length=100, description="IANA schedule time zone."
    )
    schedule: list[str] = Field(
        default_factory=lambda: ["08:00", "14:00", "20:00"],
        min_length=3,
        max_length=3,
        description="Three distinct daily HH:MM times.",
    )
    editorial_policy: str = Field(
        default="BKS Lab: практическая AI-разработка, архитектура, управление IT-проектами, доступность и критический анализ влияния технологий.",
        min_length=1,
        max_length=12000,
        description="Editorial audience and inclusion policy.",
    )
    exclusions: str = Field(
        default="Реклама без технических подробностей; непроверяемые обещания; дубли; материалы без отношения к тематике.",
        max_length=6000,
        description="Editorial exclusions.",
    )
    news_weights: ScoreWeights = Field(
        default_factory=lambda: ScoreWeights(
            topical_fit=40, significance=25, freshness=25, article_potential=10
        ),
        description="Short news score weights.",
    )
    article_weights: ScoreWeights = Field(
        default_factory=lambda: ScoreWeights(
            topical_fit=35, significance=25, freshness=10, article_potential=30
        ),
        description="Long article score weights.",
    )
    initial_lookback_days: int = Field(
        default=30, ge=1, le=365, description="First collection lookback."
    )
    max_items_per_source: int = Field(
        default=50, ge=1, le=200, description="Maximum materials per source fetch."
    )
    max_excerpt_chars: int = Field(
        default=3000,
        ge=500,
        le=12000,
        description="Maximum cleaned text sent to the model.",
    )
    analysis_batch_size: int = Field(
        default=20, ge=1, le=200, description="Maximum items queued per analysis pass."
    )
    text_retention_days: int = Field(
        default=90, ge=1, le=3650, description="Collected text retention."
    )
    history_retention_days: int = Field(
        default=180, ge=1, le=3650, description="Superseded history retention."
    )

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError("Unknown IANA timezone") from error
        return value

    @field_validator("schedule")
    @classmethod
    def validate_schedule(cls, value: list[str]) -> list[str]:
        if len(set(value)) != 3 or any(
            re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", slot) is None for slot in value
        ):
            raise ValueError("Provide three distinct HH:MM times")
        return sorted(value)


class SettingsPatch(NewsPatch):
    enabled: bool | None = None
    timezone: str | None = Field(default=None, max_length=100)
    schedule: list[str] | None = Field(default=None, min_length=3, max_length=3)
    editorial_policy: str | None = Field(default=None, min_length=1, max_length=12000)
    exclusions: str | None = Field(default=None, max_length=6000)
    news_weights: ScoreWeights | None = None
    article_weights: ScoreWeights | None = None
    initial_lookback_days: int | None = Field(default=None, ge=1, le=365)
    max_items_per_source: int | None = Field(default=None, ge=1, le=200)
    max_excerpt_chars: int | None = Field(default=None, ge=500, le=12000)
    analysis_batch_size: int | None = Field(default=None, ge=1, le=200)
    text_retention_days: int | None = Field(default=None, ge=1, le=3650)
    history_retention_days: int | None = Field(default=None, ge=1, le=3650)


class SettingsRow(NewsSettingsData):
    llm_configured: bool = Field(
        description="Provider configuration is present; no live probe."
    )
    llm_provider: str = Field(description="Provider label.")
    llm_model: str = Field(description="Configured model identifier.")


class CollectRequest(NewsRequest):
    source_id: PositiveID | None = Field(
        default=None, description="One source, or all active sources."
    )


class QueuedJob(BaseModel):
    job_id: int
    status: str


class JobRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    kind: Literal["collect", "discover", "analyze"]
    status: Literal["queued", "running", "completed", "failed", "cancelled"]
    source_id: int | None
    item_id: int | None
    attempts: int
    progress: dict
    error: str | None
    result: dict | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    heartbeat_at: datetime | None


class DecisionRequest(NewsRequest):
    decision: NewsDecision = Field(
        description="Editorial disposition.", examples=["in_work"]
    )
    format: NewsFormat = Field(
        description="Planned material format.", examples=["longread_candidate"]
    )
    comment: str = Field(
        default="", max_length=2000, description="Optional editor note.", examples=[""]
    )


class DecisionRow(DecisionRequest):
    model_config = ConfigDict(from_attributes=True)
    id: int
    item_id: int
    editor: str
    created_at: datetime


class AnalysisRow(BaseModel):
    id: int
    is_relevant: bool
    category_id: int | None
    category_name: str | None
    topics: list[CatalogRow]
    suggested_topics: list[str]
    scores: dict[str, int]
    summary_ru: str
    editorial_comment_ru: str
    recommended_formats: list[NewsFormat]
    confidence: float
    needs_verification: bool
    news_score: float
    article_score: float
    model: str
    prompt_version: str
    created_at: datetime


class ItemRow(BaseModel):
    id: int
    source_id: int
    source_name: str
    url: str
    canonical_url: str | None
    title: str
    excerpt: str
    published_at: datetime | None
    first_seen_at: datetime
    last_seen_at: datetime
    updated_at: datetime | None
    status: NewsStatus
    duplicate_of_id: int | None
    analysis: AnalysisRow | None
    decision: DecisionRow | None


class ItemDetail(ItemRow):
    content: str
    analysis_history: list[AnalysisRow]
    decision_history: list[DecisionRow]


class RunRow(BaseModel):
    id: int
    source_id: int
    source_name: str
    job_id: int | None
    status: str
    started_at: datetime
    completed_at: datetime | None
    new_count: int
    updated_count: int
    unchanged_count: int
    error: str | None
