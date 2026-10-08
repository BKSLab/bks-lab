"""Technical configuration for the isolated news scheduler and API facade."""

import re
from pathlib import Path
from tempfile import gettempdir
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class NewsSettings(BaseSettings):
    """Environment defaults; editorial settings can be overridden in PostgreSQL."""

    model_config = SettingsConfigDict(
        env_prefix="NEWS_", env_file=".env", extra="ignore", hide_input_in_errors=True
    )

    enabled: bool = True
    timezone: str = "Europe/Samara"
    schedule: tuple[str, str, str] = ("08:00", "14:00", "20:00")
    http_concurrency: int = Field(default=5, ge=1, le=20)
    http_timeout_seconds: float = Field(default=20, gt=0, le=120)
    http_max_response_bytes: int = Field(default=2 * 1024 * 1024, ge=1024, le=20 * 1024 * 1024)
    http_max_redirects: int = Field(default=5, ge=0, le=10)
    http_retries: int = Field(default=2, ge=1, le=5)
    source_min_interval_seconds: float = Field(default=1, ge=0, le=60)

    llm_provider: str = "polza"
    llm_model: str = ""
    llm_api_url: str = Field(default="", repr=False)
    llm_api_key: SecretStr = Field(default=SecretStr(""), repr=False)
    llm_concurrency: int = Field(default=1, ge=1, le=2)
    llm_timeout_seconds: float = Field(default=60, gt=0, le=300)
    llm_max_tokens: int = Field(default=1800, ge=128, le=8192)
    llm_retries: int = Field(default=2, ge=1, le=5)

    initial_lookback_days: int = Field(default=30, ge=1, le=365)
    max_items_per_source: int = Field(default=50, ge=1, le=200)
    max_excerpt_chars: int = Field(default=3000, ge=500, le=12000)
    analysis_batch_size: int = Field(default=20, ge=1, le=200)
    text_retention_days: int = Field(default=90, ge=1, le=3650)
    history_retention_days: int = Field(default=180, ge=1, le=3650)

    queue_poll_seconds: float = Field(default=5, gt=0, le=60)
    lease_seconds: int = Field(default=120, ge=15, le=3600)
    heartbeat_seconds: float = Field(default=20, gt=0, le=300)
    job_max_attempts: int = Field(default=3, ge=1, le=10)
    job_retry_delay_seconds: float = Field(default=60, ge=0, le=3600)
    settings_refresh_seconds: float = Field(default=30, ge=1, le=300)
    maintenance_interval_seconds: float = Field(default=3600, ge=30, le=86400)
    shutdown_grace_seconds: float = Field(default=30, ge=0, le=300)
    health_file: Path = Field(default_factory=lambda: Path(gettempdir()) / "news-analyzer-health")
    health_max_age_seconds: float = Field(default=120, ge=15, le=3600)

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        """Reject unknown time zones before the scheduler starts."""
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError("Use an installed IANA time zone") from error
        return value

    @field_validator("schedule")
    @classmethod
    def validate_schedule(cls, value: tuple[str, str, str]) -> tuple[str, str, str]:
        """Keep exactly three distinct daily starts in chronological order."""
        if len(set(value)) != 3 or any(
            re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", slot) is None
            for slot in value
        ):
            raise ValueError("Provide three distinct times in HH:MM format")
        return tuple(sorted(value))

    @field_validator("llm_api_url")
    @classmethod
    def validate_llm_url(cls, value: str) -> str:
        """Provider credentials belong in the key, never in a URL."""
        if not value:
            return value
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("LLM API URL must be HTTPS without credentials or query")
        return value.rstrip("/")

    @model_validator(mode="after")
    def validate_worker_timing(self) -> "NewsSettings":
        """Allow enough lease time for heartbeat delays and graceful shutdown."""
        if self.heartbeat_seconds * 2 >= self.lease_seconds:
            raise ValueError("Heartbeat interval must be less than half the lease")
        if self.health_max_age_seconds <= self.settings_refresh_seconds * 2:
            raise ValueError("Health timeout must exceed two settings refresh intervals")
        return self

    @property
    def llm_configured(self) -> bool:
        """Expose readiness without exposing provider credentials."""
        return bool(self.llm_api_key.get_secret_value() and self.llm_model and self.llm_api_url)
