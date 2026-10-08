"""Schemas for the public stats endpoint."""

from pydantic import BaseModel, ConfigDict, Field

# Mirrors StatsSettings.path_max_length; duplicated here to keep schemas
# importable without a configured environment.
_PATH_MAX_LENGTH = 500


class PageViewRequest(BaseModel):
    """Beacon payload sent by the frontend PageViewTracker."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"path": "/blog/post/1c-async", "referrer": "https://google.com/"}
        }
    )

    path: str = Field(
        ...,
        min_length=1,
        max_length=_PATH_MAX_LENGTH,
        description="Relative site path; may include query string and a #note-<slug> anchor.",
        examples=["/blog/post/1c-async"],
    )
    referrer: str | None = Field(
        None,
        max_length=2048,
        description="Document referrer; only the domain is stored.",
        examples=["https://google.com/"],
    )
