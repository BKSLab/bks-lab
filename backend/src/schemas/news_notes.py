"""Automatic note candidate, administration and durable publication settings."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

QueueStatus = Literal["queued", "published", "excluded", "expired"]


class NoteCandidate(BaseModel):
    """One bounded plain-text Russian candidate from the existing LLM call."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=90, description="Russian title; up to 90 characters including spaces.")
    text: str = Field(min_length=1, max_length=300, description="Russian note body; up to 300 characters including spaces.")

    @field_validator("title", "text")
    @classmethod
    def plain_russian_text(cls, value: str) -> str:
        """Reject unsupported language and markup instead of silently truncating."""
        import re

        if not re.search(r"[А-Яа-яЁё]", value):
            raise ValueError("Russian text required")
        if re.search(r"https?://|<[^>]+>|\[[^\]]+\]\(|::ad", value, re.IGNORECASE):
            raise ValueError("Plain text without links required")
        return value


class NoteSettingsPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool | None = Field(None, strict=True, description="Enable automatic publication.")
    interval_minutes: int | None = Field(None, strict=True, ge=10, le=1440, description="Minimum interval between publications.")
    max_age_hours: int | None = Field(None, strict=True, ge=1, le=720, description="Maximum source age and queue waiting age.")

    @field_validator("enabled", "interval_minutes", "max_age_hours", mode="before")
    @classmethod
    def nonnull(cls, value):
        if value is None:
            raise ValueError("Explicit null is not supported")
        return value


class NoteSettingsRow(BaseModel):
    enabled: bool = Field(description="Automatic publication enabled.")
    interval_minutes: int = Field(description="Minimum interval between publications.")
    max_age_hours: int = Field(description="Maximum source age and waiting age.")
    started_at: datetime | None = Field(description="First activation; never reset by pause/resume.")
    last_published_at: datetime | None = Field(description="Most recent queued-note publication.")
    next_publish_at: datetime | None = Field(description="Earliest next publication time; null when paused.")
    queued: int = Field(description="Queued note count.")
    published: int = Field(description="Published note count.")
    excluded: int = Field(description="Excluded note count.")
    expired: int = Field(description="Expired note count.")


class NoteQueuePatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str | None = Field(None, min_length=1, max_length=90, description="Updated title, at most 90 characters.")
    text: str | None = Field(None, min_length=1, max_length=300, description="Updated body, at most 300 characters.")
    status: Literal["queued", "excluded"] | None = Field(None, description="Queue or exclude this draft.")

    @field_validator("title", "text", "status", mode="before")
    @classmethod
    def nonnull(cls, value):
        if value is None:
            raise ValueError("Explicit null is not supported")
        return value


class NoteQueueRow(BaseModel):
    note_slug: str = Field(description="Stable note address.")
    content_id: int | None = Field(description="Editor content ID; null after deletion.")
    title: str = Field(description="Current note title.")
    text: str = Field(description="Current note body as plain text.")
    source_name: str = Field(description="Original source name snapshot.")
    source_url: str = Field(description="Exact original article link.")
    status: QueueStatus = Field(description="Queue disposition.")
    created_at: datetime = Field(description="Queued at.")
    published_at_time: datetime | None = Field(description="Actual publication instant.")
    reason: str | None = Field(description="Disposition reason, when present.")
