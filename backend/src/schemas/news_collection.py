"""Transport-neutral results shared by source adapters and background jobs."""

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class CollectedItem:
    external_id: str | None
    url: str
    canonical_url: str
    title: str
    description: str = ""
    content: str = ""
    published_at: datetime | None = None
    updated_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert dates for the JSON preview stored in a job result."""
        result = asdict(self)
        for key in ("published_at", "updated_at"):
            value = result[key]
            result[key] = value.isoformat() if value else None
        return result


@dataclass(frozen=True)
class CollectionResult:
    items: list[CollectedItem]
    etag: str | None = None
    last_modified: str | None = None
    not_modified: bool = False
    url: str = ""
    kind: str = "rss"
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DiscoveryResult:
    kind: str
    url: str
    items: list[CollectedItem]
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return the bounded, plain-text preview for the admin interface."""
        return {"kind": self.kind, "url": self.url,
                "items": [item.to_dict() for item in self.items[:5]],
                "warnings": self.warnings}
