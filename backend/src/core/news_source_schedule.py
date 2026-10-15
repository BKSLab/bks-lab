"""Calendar calculations shared by source preferences and the durable queue."""

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from src.schemas.news_source_schedule import (
    IntervalDaysSourceSchedule,
    SourceSchedule,
    WeeklySourceSchedule,
    source_schedule_adapter,
)

SOURCE_TIMEZONE = "Europe/Samara"
SOURCE_SCHEDULE_LOCK = 721409082
DEFAULT_SOURCE_SCHEDULE = {"mode": "daily", "times": ["08:00", "14:00", "20:00"]}


def validate_source_schedule(value: dict | SourceSchedule) -> SourceSchedule:
    """Validate and normalize a saved source calendar."""
    return source_schedule_adapter.validate_python(value)


def _eligible_date(schedule: SourceSchedule, day: date) -> bool:
    if isinstance(schedule, IntervalDaysSourceSchedule):
        delta = (day - schedule.start_date).days
        return delta >= 0 and delta % schedule.every_days == 0
    if isinstance(schedule, WeeklySourceSchedule):
        return day.weekday() in schedule.weekdays
    return True


def _aware(now: datetime) -> datetime:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Source schedule calculations require an aware datetime")
    return now.astimezone(ZoneInfo(SOURCE_TIMEZONE))


def next_scheduled_check(value: dict | SourceSchedule, after: datetime) -> datetime:
    """Return the first calendar start strictly after an aware timestamp, in UTC."""
    schedule = validate_source_schedule(value)
    local = _aware(after)
    first_day = local.date()
    if isinstance(schedule, IntervalDaysSourceSchedule):
        first_day = max(first_day, schedule.start_date)
    for offset in range(366):
        day = first_day + timedelta(days=offset)
        if not _eligible_date(schedule, day):
            continue
        for slot in schedule.times:
            candidate = datetime.combine(day, time.fromisoformat(slot), tzinfo=local.tzinfo)
            if candidate > local:
                return candidate.astimezone(timezone.utc)
    raise ValueError("Source calendar has no next start")


def latest_scheduled_check(value: dict | SourceSchedule, at: datetime) -> datetime | None:
    """Return the most recent calendar start, coalescing missed starts after a restart."""
    schedule = validate_source_schedule(value)
    local = _aware(at)
    for offset in range(366):
        day = local.date() - timedelta(days=offset)
        if isinstance(schedule, IntervalDaysSourceSchedule) and day < schedule.start_date:
            return None
        if not _eligible_date(schedule, day):
            continue
        for slot in reversed(schedule.times):
            candidate = datetime.combine(day, time.fromisoformat(slot), tzinfo=local.tzinfo)
            if candidate <= local:
                return candidate.astimezone(timezone.utc)
    return None
