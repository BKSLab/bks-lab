"""Restricted source calendars in the fixed editorial time zone."""

import re
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator


class SourceTimes(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    times: list[Annotated[str, Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")]] = Field(
        min_length=1, max_length=12,
        description="Distinct daily HH:MM starts in Europe/Samara.", examples=[["08:00", "20:00"]],
    )

    @field_validator("times")
    @classmethod
    def distinct_times(cls, values: list[str]) -> list[str]:
        if len(set(values)) != len(values):
            raise ValueError("Provide distinct HH:MM times")
        return sorted(values)


class DailySourceSchedule(SourceTimes):
    mode: Literal["daily"] = Field(description="Run every day.", examples=["daily"])


class IntervalDaysSourceSchedule(SourceTimes):
    mode: Literal["interval_days"] = Field(description="Run every N days from a fixed date.", examples=["interval_days"])
    every_days: int = Field(ge=1, le=365, strict=True, description="Days between collection dates.", examples=[3])
    start_date: date = Field(description="First collection date in Europe/Samara.", examples=["2026-10-15"])

    @field_validator("start_date", mode="before")
    @classmethod
    def plain_start_date(cls, value: object) -> object:
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if not isinstance(value, str) or re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) is None:
            raise ValueError("Use a calendar date in YYYY-MM-DD format")
        return value


class WeeklySourceSchedule(SourceTimes):
    mode: Literal["weekly"] = Field(description="Run on selected weekdays.", examples=["weekly"])
    weekdays: list[Annotated[int, Field(ge=0, le=6, strict=True)]] = Field(
        min_length=1, max_length=7,
        description="Distinct weekdays, Monday 0 through Sunday 6.", examples=[[0, 3]],
    )

    @field_validator("weekdays")
    @classmethod
    def distinct_weekdays(cls, values: list[int]) -> list[int]:
        if len(set(values)) != len(values):
            raise ValueError("Provide distinct weekdays")
        return sorted(values)


SourceSchedule = Annotated[
    DailySourceSchedule | IntervalDaysSourceSchedule | WeeklySourceSchedule,
    Field(discriminator="mode"),
]
source_schedule_adapter = TypeAdapter(SourceSchedule)
