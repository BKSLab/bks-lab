"""Readable, stable addresses for source and queue records."""

import re
import unicodedata
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

SOURCE_SLUG_MAX = 160
JOB_SLUG_MAX = 240
SAMARA = ZoneInfo("Europe/Samara")
_RUSSIAN = str.maketrans(
    dict(zip(
        "абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
        (
            "a", "b", "v", "g", "d", "e", "yo", "zh", "z", "i", "y", "k", "l", "m",
            "n", "o", "p", "r", "s", "t", "u", "f", "kh", "ts", "ch", "sh", "shch",
            "", "y", "", "e", "yu", "ya",
        ),
    ))
)


def readable_slug(value: str, *, fallback: str = "source", limit: int = SOURCE_SLUG_MAX) -> str:
    """Transliterate Russian names and normalize accented Latin into URL-safe ASCII."""
    value = unicodedata.normalize("NFKD", value.casefold().translate(_RUSSIAN))
    value = "".join(character for character in value if not unicodedata.combining(character))
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")[:limit].rstrip("-")
    if not value:
        return fallback
    return f"{fallback}-{value}"[:limit] if value.isdecimal() else value


def job_slug_base(kind: str, scope: str, *, created_at: datetime | None = None) -> str:
    """Build an enqueue-time address with a fixed Europe/Samara calendar timestamp."""
    created_at = created_at or datetime.now(timezone.utc)
    stamp = created_at.astimezone(SAMARA).strftime("%Y-%m-%d-%H%M%S")
    prefix = scope if kind == "collect" else f"{kind}-{scope}"
    return f"{prefix[:JOB_SLUG_MAX - len(stamp) - 1].rstrip('-')}-{stamp}"
