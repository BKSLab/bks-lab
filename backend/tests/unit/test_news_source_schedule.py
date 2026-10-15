"""Source calendars use one stable wall clock and reject unsupported schedules."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.core.news_source_schedule import (
    latest_scheduled_check, next_scheduled_check, validate_source_schedule,
)


def utc(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


@pytest.mark.parametrize(("schedule", "now", "next_start", "previous"), [
    ({"mode": "daily", "times": ["20:00", "08:00"]}, "2026-10-15T03:59:00", "2026-10-15T04:00:00", "2026-10-14T16:00:00"),
    ({"mode": "daily", "times": ["08:00", "20:00"]}, "2026-10-15T04:00:00", "2026-10-15T16:00:00", "2026-10-15T04:00:00"),
    ({"mode": "daily", "times": ["00:00"]}, "2026-10-15T19:59:00", "2026-10-15T20:00:00", "2026-10-14T20:00:00"),
    ({"mode": "weekly", "times": ["08:00", "20:00"], "weekdays": [0, 3]}, "2026-10-15T17:00:00", "2026-10-19T04:00:00", "2026-10-15T16:00:00"),
    ({"mode": "interval_days", "times": ["08:00"], "every_days": 3, "start_date": "2026-10-10"}, "2026-10-15T10:00:00", "2026-10-16T04:00:00", "2026-10-13T04:00:00"),
    ({"mode": "interval_days", "times": ["08:00"], "every_days": 365, "start_date": "2026-10-15"}, "2026-10-15T04:00:00", "2027-10-15T04:00:00", "2026-10-15T04:00:00"),
    ({"mode": "interval_days", "times": ["08:00"], "every_days": 3, "start_date": "2030-10-10"}, "2026-10-15T10:00:00", "2030-10-10T04:00:00", None),
])
def test_calendar_resolves_next_start_and_latest_missed_start(schedule, now, next_start, previous):
    assert next_scheduled_check(schedule, utc(now)) == utc(next_start)
    assert latest_scheduled_check(schedule, utc(now)) == (utc(previous) if previous else None)


def test_calendar_rejects_naive_clock_and_does_not_backfill_before_anchor():
    schedule = {"mode": "interval_days", "times": ["08:00"], "every_days": 2, "start_date": "2026-10-15"}
    assert latest_scheduled_check(schedule, utc("2026-10-15T03:59:59")) is None
    with pytest.raises(ValueError, match="aware"):
        next_scheduled_check(schedule, datetime(2026, 10, 15))


@pytest.mark.parametrize("schedule", [
    {"mode": "daily", "times": ["24:00"]},
    {"mode": "daily", "times": ["08:00", "08:00"]},
    {"mode": "daily", "times": [f"{hour:02}:00" for hour in range(13)]},
    {"mode": "weekly", "times": ["08:00"], "weekdays": [True]},
    {"mode": "weekly", "times": ["08:00"], "weekdays": [0, 0]},
    {"mode": "interval_days", "times": ["08:00"], "every_days": True, "start_date": "2026-10-15"},
    {"mode": "interval_days", "times": ["08:00"], "every_days": 2},
    {"mode": "interval_days", "times": ["08:00"], "every_days": 2, "start_date": "2026-02-30"},
    {"mode": "interval_days", "times": ["08:00"], "every_days": 2, "start_date": "2026-10-15T00:00:00"},
    {"mode": "cron", "times": ["08:00"]},
])
def test_calendar_rejects_ambiguous_or_unsupported_values(schedule):
    with pytest.raises(ValidationError):
        validate_source_schedule(schedule)
