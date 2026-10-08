"""Public shape of the protected, read-only Admin API."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr

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


class ContentItemDetail(ContentItemRow):
    synced_at: datetime
    content_hash: str
    views_timeseries_30d: list[TimeseriesPoint]


class SubscriberRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    email: str
    subscribed_at: datetime
