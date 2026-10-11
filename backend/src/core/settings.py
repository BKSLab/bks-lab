"""Application configuration via pydantic-settings.

Reads `backend/.env` (working directory of the backend process).
`SecretStr` is used only for real secrets.
"""

from functools import lru_cache
from ipaddress import IPv4Network, IPv6Network
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

from src.core.news_settings import NewsSettings

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_", env_file=".env", extra="ignore"
    )

    name: str = "BKS Lab"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"
    # JSON array of proxy IP addresses/CIDRs; no forwarded headers are
    # trusted until the deployment explicitly configures its proxy peers.
    trusted_proxies: tuple[IPv4Network | IPv6Network, ...] = ()


class DBSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    postgres_user: str = "bkslab"
    postgres_password: SecretStr = Field(default=SecretStr("bkslab-dev-password"))
    postgres_db: str = "bkslab"
    # Host/port differ between local run (localhost:5434) and Docker (db:5432).
    postgres_host: str = "localhost"
    postgres_port: int = 5434

    @property
    def database_url(self) -> str:
        return URL.create(
            "postgresql+asyncpg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        ).render_as_string(hide_password=False)


class ContentSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CONTENT_", env_file=".env", extra="ignore"
    )

    # Directory with Markdown content (articles/notes/projects subdirectories);
    # read only by the one-time importer, never by the running application.
    dir: Path = BACKEND_ROOT / "content"
    # Words per minute used to derive reading_time from word_count.
    words_per_minute: int = 200


class MediaSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MEDIA_", env_file=".env", extra="ignore"
    )

    # Uploaded images root; served at /uploads/ (backend in dev, nginx in prod).
    dir: Path = BACKEND_ROOT / "uploads"
    # Reject larger originals before decoding.
    max_bytes: int = Field(default=5 * 1024 * 1024, ge=1)
    # Wider images are downscaled; height follows the aspect ratio.
    max_width: int = Field(default=1920, ge=100)


class RevalidateSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="REVALIDATE_", env_file=".env", extra="ignore", populate_by_name=True
    )

    # Base URL of the frontend container, e.g. http://frontend:3000;
    # the webhook is POST {frontend_internal_url}/api/revalidate.
    frontend_internal_url: str | None = Field(
        default=None, validation_alias="FRONTEND_INTERNAL_URL"
    )
    # Bearer secret shared with the frontend revalidate route.
    secret: SecretStr | None = None

    @property
    def configured(self) -> bool:
        """Both halves of the pair must be set for the webhook to run."""
        return bool(
            self.frontend_internal_url
            and self.secret
            and self.secret.get_secret_value()
        )


class StatsSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="STATS_", env_file=".env", extra="ignore"
    )

    # Master secret for visitor hashing; daily salt is derived as
    # HMAC_SHA256(stats_secret, current UTC date), so no rotation job is needed.
    secret: SecretStr
    pageview_rate_limit: str = "60/minute"
    path_max_length: int = 500
    referrer_domain_max_length: int = 255


class AdminSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ADMIN_", env_file=".env", extra="ignore"
    )

    username: str = ""
    password: SecretStr = SecretStr("")
    allowed_origins: tuple[str, ...] = ()
    cookie_secure: bool = True
    session_ttl_seconds: int = Field(default=43200, ge=60)
    cleanup_interval_seconds: int = Field(default=3600, ge=60)

    @field_validator("allowed_origins")
    @classmethod
    def validate_origins(cls, origins: tuple[str, ...]) -> tuple[str, ...]:
        """Accept explicit origins only; Host headers never grant access."""
        for origin in origins:
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path
                or parsed.query
                or parsed.fragment
                or origin != f"{parsed.scheme}://{parsed.netloc}"
            ):
                raise ValueError("Admin origins must be exact http(s) origins without a path")
        return origins


class SMTPSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SMTP_", env_file=".env", extra="ignore"
    )

    host: str = ""
    port: int = Field(default=587, ge=1, le=65535)
    username: str = ""
    password: SecretStr = SecretStr("")
    sender: str = ""
    recipient: str = ""
    use_tls: bool = False
    start_tls: bool = True
    timeout: float = Field(default=10, gt=0, le=60)

    @model_validator(mode="after")
    def validate_tls(self) -> "SMTPSettings":
        """Implicit TLS and STARTTLS are mutually exclusive."""
        if self.use_tls and self.start_tls:
            raise ValueError("Set SMTP_START_TLS=false when SMTP_USE_TLS=true")
        return self


class Settings:
    """Aggregator for domain-specific settings groups."""

    def __init__(self) -> None:
        self.app = AppSettings()
        self.db = DBSettings()
        self.content = ContentSettings()
        self.media = MediaSettings()
        self.revalidate = RevalidateSettings()
        self.stats = StatsSettings()
        self.admin = AdminSettings()
        self.smtp = SMTPSettings()
        self.news = NewsSettings()


@lru_cache
def get_settings() -> Settings:
    return Settings()
