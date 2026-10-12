"""Source suggestions for the catalogue UI and validated startup seed."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.schemas.news import SourceURL


class SourceCatalogueEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str = Field(
        min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$",
        description="Stable research entry ID.", examples=["labs-openai"],
    )
    group: Literal["labs", "engineering", "business", "society", "authors", "russian", "tools"] = Field(
        description="Research catalogue section.", examples=["labs"],
    )
    name: str = Field(
        min_length=1, max_length=200, description="Display name.", examples=["OpenAI News"],
    )
    url: SourceURL = Field(
        description="Suggested primary URL; discovery is required before connection.",
        examples=["https://openai.com/news/"],
    )
    feed_url: SourceURL | None = Field(
        default=None, alias="feedUrl", description="Known feed URL, if present.",
        examples=["https://example.org/feed.xml"],
    )
    extra_urls: list[SourceURL] = Field(
        alias="extraUrls", description="Additional research addresses.", examples=[[]],
    )
    priority: Literal["A", "B", "C"] | None = Field(
        description="Research priority, independent of collection settings.", examples=["A"],
    )
    connection: str = Field(
        max_length=4000, description="Research connection notes.", examples=["HTML, autodiscovery RSS"],
    )
    description: str = Field(
        max_length=4000, description="Research description.", examples=["AI research and releases."],
    )
    mode: Literal["rss", "auto", "read", "api"] = Field(
        description="Suggested usage, including resources not supported for collection.", examples=["auto"],
    )
    vendor: bool = Field(
        description="Suggestion is affiliated with an AI vendor.", examples=[True],
    )
