"""Validated editor requests and safe News Analyzer responses."""

import re
from datetime import datetime
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from src.schemas.news_source_schedule import SourceSchedule

NewsFormat = Literal["longread_candidate", "short_news_candidate"]
NewsDecision = Literal["in_work", "deferred", "rejected"]
NewsStatus = Literal["pending_analysis", "analyzed"]
NewsKind = Literal["rss", "html"]
def validate_news_slug(value: str) -> str:
    """Reject numeric record IDs as public news addresses."""
    if re.search(r"[a-z]", value) is None:
        raise ValueError("Use a readable news slug")
    return value


NewsSlug = Annotated[str, Field(min_length=1, max_length=240, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$"), AfterValidator(validate_news_slug)]
RunOutcome = Literal["new", "updated", "unchanged", "skipped"]


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


class SourcePatch(NewsPatch):
    active: bool | None = Field(
        default=None, description="Enable automatic collection for this source.", examples=[True]
    )
    schedule: SourceSchedule | None = Field(
        default=None, description="Collection calendar in Europe/Samara.",
        examples=[{"mode": "daily", "times": ["08:00", "20:00"]}],
    )


class SourceRow(BaseModel):
    id: int = Field(description="Internal source identity.", examples=[1])
    slug: str = Field(description="Stable readable source address.", examples=["labs-huggingface"])
    name: str = Field(description="Source display name.", examples=["Hugging Face Blog"])
    description: str = Field(description="Editorial source description.", examples=["AI engineering and research."])
    url: str = Field(description="Source collection URL.", examples=["https://huggingface.co/blog/feed.xml"])
    active: bool = Field(description="Automatic collection is enabled.", examples=[False])
    schedule: SourceSchedule = Field(description="Collection calendar in Europe/Samara.")
    next_check_at: datetime | None = Field(description="Next automatic collection start, or null when paused.")
    last_success_at: datetime | None = Field(description="Last successful collection.")
    last_error: str | None = Field(description="Safe latest collection error.")
    last_new_count: int = Field(description="New materials in the latest collection.", examples=[0])
    health: str = Field(description="Latest collection health.", examples=["unknown"])


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

class SettingsPatch(NewsPatch):
    enabled: bool | None = None
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
    source_slug: NewsSlug | None = Field(
        default=None, description="One source, or all active sources."
    )


class QueuedJob(BaseModel):
    job_id: int
    job_slug: str = Field(description="Stable job address for polling and reports.", examples=["all-sources-2026-10-15-142030"])
    status: str


class JobRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    slug: str = Field(description="Stable readable job address.", examples=["example-2026-10-15-142030"])
    kind: Literal["collect", "discover", "analyze"]
    status: Literal["queued", "running", "completed", "failed", "cancelled"]
    source_id: int | None
    source_name: str | None = Field(description="Current name of the scoped source.", examples=["Example"])
    source_slug: str | None = Field(description="Stable source address.", examples=["example"])
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
    source_slug: str = Field(description="Stable address of the owning source.", examples=["example"])
    url: str
    canonical_url: str | None
    title: str
    excerpt: str
    published_at: datetime | None
    first_seen_at: datetime
    last_seen_at: datetime
    updated_at: datetime | None
    status: NewsStatus
    analysis_state: Literal["analyzed", "queued", "running", "failed", "insufficient_text", "pending"] = Field(
        description="Actual state of processing the current material."
    )
    analysis_error: str | None = Field(default=None, description="Safe terminal analysis error.")
    collection_warning: str | None = Field(default=None, description="Safe warning from the latest text fetch.")
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
    source_slug: str = Field(description="Source address captured when the run began.", examples=["example"])
    source_url: str = Field(description="Source URL captured when the run began.", examples=["https://example.org/feed.xml"])
    source_kind: NewsKind = Field(description="Adapter captured when the run began.", examples=["rss"])
    job_id: int | None
    job_slug: str | None = Field(description="Owning job address.", examples=["example-2026-10-15-142030"])
    status: str
    started_at: datetime
    completed_at: datetime | None
    new_count: int
    updated_count: int
    unchanged_count: int
    skipped_count: int = Field(description="Candidates skipped during collection.", examples=[2])
    warning_count: int = Field(description="Observations with collection warnings.", examples=[1])
    parameters: dict = Field(description="Safe collection parameters captured for this attempt.", examples=[{}])
    not_modified: bool = Field(description="Source responded to a conditional request with no changes.", examples=[False])
    http_status: int | None = Field(description="Source HTTP response status if available.", examples=[200])
    limit_reached: bool = Field(description="Configured collection limit was reached.", examples=[False])
    diagnostics_truncated: bool = Field(description="Candidate diagnostics were capped.", examples=[False])
    error: str | None


class RunItemRow(BaseModel):
    """Historical collection observation with version-specific analysis state."""

    id: int = Field(description="Internal observation key.", examples=[1])
    run_id: int = Field(description="Internal source run key.", examples=[1])
    source_name: str = Field(description="Source name captured at run start.", examples=["Example"])
    source_slug: str = Field(description="Stable source address.", examples=["example"])
    title: str = Field(description="Title observed during this run.", examples=["A new release"])
    url: str | None = Field(description="Candidate URL, when valid and available.", examples=["https://example.org/release"])
    item_id: int | None = Field(description="Retained material key, if any.", examples=[1])
    outcome: RunOutcome = Field(description="Ingestion result for this candidate.", examples=["unchanged"])
    reason: str | None = Field(description="Safe reason for the outcome.", examples=["Outside the collection window."])
    warning: str | None = Field(description="Safe collection warning.", examples=["Article text could not be fetched."])
    stage: str | None = Field(description="Stage responsible for the diagnostic.", examples=["article"])
    preserved_previous: bool = Field(description="Earlier sufficient text was preserved.", examples=[False])
    analysis_status: Literal["queued", "running", "completed", "failed", "cancelled", "pending", "skipped"] | None = Field(description="Analysis state for this exact observed version.", examples=["queued"])
    analysis_reason: str | None = Field(default=None, max_length=500, description="Safe explanation when an analysis job finished without a saved result.", examples=["Версия материала изменилась до завершения анализа."])
    analysis_job_slug: str | None = Field(description="Latest analysis job address for this version, if retained.", examples=[None])
