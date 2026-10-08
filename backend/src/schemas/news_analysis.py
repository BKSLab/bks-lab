"""Strict classification output; scores and allowed identities are validated."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Score = Annotated[int, Field(strict=True, ge=0, le=100)]
NewsFormat = Literal["short_news_candidate", "longread_candidate"]


class NewsScores(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topical_fit: Score
    significance: Score
    freshness: Score
    article_potential: Score


class NewsAnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_relevant: bool = Field(strict=True)
    category_id: int | None = Field(ge=1)
    topic_ids: list[Annotated[int, Field(strict=True, ge=1)]] = Field(max_length=20)
    suggested_topics: list[Annotated[str, Field(min_length=1, max_length=100)]] = Field(max_length=5)
    scores: NewsScores
    summary_ru: str = Field(min_length=1, max_length=500)
    editorial_comment_ru: str = Field(min_length=1, max_length=600)
    recommended_formats: list[NewsFormat] = Field(max_length=2)
    confidence: float = Field(ge=0, le=1)
    needs_verification: bool = Field(strict=True)
