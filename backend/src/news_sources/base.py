"""Code-owned collection profiles; external input never defines selectors."""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date
from typing import Literal


@dataclass(frozen=True)
class SourceProfile:
    """Describe one supported publisher and its verified collection layout."""

    id: str
    slug: str
    name: str
    description: str
    homepage_url: str
    url: str
    kind: Literal["rss", "html"]
    config: dict[str, str] = field(default_factory=dict)
    default_schedule: dict = field(default_factory=lambda: {
        "mode": "daily", "times": ["08:00", "20:00"],
    })
    priority: int = 50
    trust_score: int = 75
    vendor_affiliated: bool = False
    article_selectors: tuple[str, ...] = ()
    article_noise_selectors: tuple[str, ...] = ()
    # Some feeds include navigation entries beside actual publications.
    publication_path_pattern: str | None = None
    research_ids: tuple[str, ...] = ()
    verified_at: date = date(2026, 10, 15)
    verification_method: str = "safe-http-list-article-repeat"
    fixture_path: str = ""

    @property
    def version(self) -> str:
        """Invalidate cached text when trusted collection rules change."""
        payload = json.dumps([
            self.url, self.kind, self.config, self.article_selectors,
            self.article_noise_selectors, self.publication_path_pattern,
        ], sort_keys=True, ensure_ascii=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()[:16]
