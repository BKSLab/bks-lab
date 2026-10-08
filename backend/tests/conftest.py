"""Shared fixtures: required PostgreSQL testcontainer,
Markdown content builders and an API client with overridden dependencies."""

import os
from collections.abc import AsyncGenerator, Iterator
from datetime import datetime, timezone
from pathlib import Path

# Test environment must be set before any application import (settings are
# read at module import time). A low pageview limit lets the rate-limit test
# run with few requests. Each test resets the in-memory limiter.
os.environ["STATS_SECRET"] = "test-stats-secret"
os.environ["STATS_PAGEVIEW_RATE_LIMIT"] = "3/minute"
os.environ["APP_TRUSTED_PROXIES"] = "[]"
os.environ["ADMIN_USERNAME"] = ""
os.environ["ADMIN_PASSWORD"] = ""
os.environ["ADMIN_ALLOWED_ORIGINS"] = "[]"
os.environ["SMTP_HOST"] = ""
os.environ["SMTP_SENDER"] = ""
os.environ["SMTP_RECIPIENT"] = ""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from main import app
from src.core.limiter import limiter
from src.db.models import (
    AdminSession, Base, ContentItem, PageView, Subscriber,
    NewsSource, NewsJob, NewsCategory, NewsTopic, NewsSetting,
)
from src.dependencies.db_session import get_db_session
from src.dependencies.repositories import (
    get_articles_repository,
    get_notes_repository,
    get_projects_repository,
)
from src.dependencies.services import get_stats_service, get_utc_now
from src.repositories.markdown_content import MarkdownContentRepository
from src.schemas.frontmatter import ArticleFrontmatter, NoteFrontmatter, ProjectFrontmatter
from src.services.stats import StatsService

# PostgreSQL is mandatory: SQLite cannot prove the production SQL semantics.

_FIXED_NOW = datetime(2026, 2, 20, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    """Start PostgreSQL or fail explicitly when its prerequisites are absent."""
    try:
        container = PostgresContainer("postgres:16-alpine")
        container.start()
    except Exception as error:
        pytest.fail(
            "PostgreSQL integration tests require a working Docker daemon and "
            f"the postgres:16-alpine image (startup failed: {type(error).__name__}). "
            "No SQLite fallback is supported.",
            pytrace=False,
        )
    try:
        yield container.get_connection_url().replace("psycopg2", "asyncpg")
    finally:
        container.stop()


@pytest_asyncio.fixture(scope="session")
async def db_engine(postgres_url: str) -> AsyncGenerator:
    engine = create_async_engine(postgres_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def session_factory(db_engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def db_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    """Per-test session; tables are wiped by the autouse cleaner."""
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture(autouse=True)
async def _clean_tables(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[None, None]:
    """Keep DB tests isolated even when code under test opens own sessions."""
    yield
    async with session_factory() as session:
        await session.execute(delete(NewsSource))
        await session.execute(delete(NewsJob))
        await session.execute(delete(NewsCategory))
        await session.execute(delete(NewsTopic))
        await session.execute(delete(NewsSetting))
        await session.execute(delete(PageView))
        await session.execute(delete(ContentItem))
        await session.execute(delete(AdminSession))
        await session.execute(delete(Subscriber))
        await session.commit()


# Markdown content builders


def write_article(
    directory: Path,
    slug: str,
    *,
    title: str = "Test article",
    category: str = "development",
    published_at: str = "2026-02-10",
    draft: bool = False,
    tags: list[str] | None = None,
    reading_time: int | None = None,
    body: str = "Body text of the test article.",
) -> Path:
    tags_yaml = "[" + ", ".join(f'"{tag}"' for tag in (tags or [])) + "]"
    reading_time_line = f"reading_time: {reading_time}\n" if reading_time is not None else ""
    content = (
        f"---\n"
        f'title: "{title}"\n'
        f'excerpt: "Excerpt of {title}"\n'
        f"category: {category}\n"
        f"published_at: {published_at}\n"
        f'cover_image: "/images/articles/{slug}.webp"\n'
        f"tags: {tags_yaml}\n"
        f"{reading_time_line}"
        f"draft: {str(draft).lower()}\n"
        f"---\n\n{body}\n"
    )
    path = directory / f"{slug}.md"
    path.write_text(content, encoding="utf-8")
    return path


def write_note(
    directory: Path,
    slug: str,
    *,
    title: str = "Test note",
    published_at: str = "2026-02-12",
    related: str | None = None,
    draft: bool = False,
    body: str = "Short note text.",
) -> Path:
    related_line = f'related: "{related}"\n' if related else ""
    content = (
        f"---\n"
        f'title: "{title}"\n'
        f"published_at: {published_at}\n"
        f"{related_line}"
        f"draft: {str(draft).lower()}\n"
        f"---\n\n{body}\n"
    )
    path = directory / f"{slug}.md"
    path.write_text(content, encoding="utf-8")
    return path


def write_project(
    directory: Path,
    slug: str,
    *,
    title: str = "Test project",
    status: str = "active",
    featured: bool = False,
    order: int = 10,
    draft: bool = False,
    body: str = "Project description.",
) -> Path:
    content = (
        f"---\n"
        f'title: "{title}"\n'
        f'excerpt: "Excerpt of {title}"\n'
        f'cover_image: "/images/projects/{slug}.webp"\n'
        f'tags: ["FastAPI"]\n'
        f"status: {status}\n"
        f"featured: {str(featured).lower()}\n"
        f"order: {order}\n"
        f"draft: {str(draft).lower()}\n"
        f"---\n\n{body}\n"
    )
    path = directory / f"{slug}.md"
    path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture
def content_dirs(tmp_path: Path) -> dict[str, Path]:
    """Content directory tree with a small valid/invalid/draft fixture set."""
    articles = tmp_path / "articles"
    notes = tmp_path / "notes"
    projects = tmp_path / "projects"
    for directory in (articles, notes, projects):
        directory.mkdir()

    write_article(articles, "article-one", title="First article", published_at="2026-02-10")
    write_article(
        articles,
        "article-two",
        title="Second article about AI",
        category="ai",
        published_at="2026-02-20",
        body="Text mentioning Async Patterns.",
    )
    write_article(articles, "article-draft", title="Draft article", draft=True)
    (articles / "broken-article.md").write_text(
        "---\nno_title: true\n---\n\nBody without required fields.\n", encoding="utf-8"
    )

    write_note(notes, "note-one", title="First note", published_at="2026-02-12")
    write_note(
        notes,
        "note-two",
        title="Second note",
        published_at="2026-02-15",
        related="article-two",
    )
    write_note(notes, "note-broken-link", title="Broken link note", related="missing-article")
    write_note(notes, "note-draft", title="Draft note", draft=True)

    write_project(projects, "project-one", title="First project", featured=True, order=1)
    write_project(projects, "project-two", title="Second project", order=2)
    write_project(projects, "project-archived", title="Old project", status="archived", order=3)
    write_project(projects, "project-draft", title="Draft project", draft=True)

    return {"article": articles, "note": notes, "project": projects}


def make_markdown_repository(
    content_type: str,
    directory: Path,
    session_factory: async_sessionmaker[AsyncSession],
) -> MarkdownContentRepository:
    """Build a Markdown repository with immediate TTL expiry (test-friendly)."""
    model = {
        "article": ArticleFrontmatter,
        "note": NoteFrontmatter,
        "project": ProjectFrontmatter,
    }[content_type]
    return MarkdownContentRepository(
        content_dir=directory,
        content_type=content_type,
        frontmatter_model=model,
        session_factory=session_factory,
        ttl_seconds=0.0,
        words_per_minute=200,
    )


@pytest_asyncio.fixture
async def client(
    content_dirs: dict[str, Path],
    session_factory: async_sessionmaker[AsyncSession],
    client_ip: str,
) -> AsyncGenerator[AsyncClient, None]:
    """API client with content repositories pointing at the tmp fixture tree."""
    articles_repo = make_markdown_repository("article", content_dirs["article"], session_factory)
    notes_repo = make_markdown_repository("note", content_dirs["note"], session_factory)
    projects_repo = make_markdown_repository("project", content_dirs["project"], session_factory)

    def stats_service_factory() -> StatsService:
        return StatsService(
            session_factory=session_factory,
            stats_secret="test-stats-secret",
            utc_now=lambda: _FIXED_NOW,
            referrer_domain_max_length=255,
        )

    async def test_db_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_articles_repository] = lambda: articles_repo
    app.dependency_overrides[get_notes_repository] = lambda: notes_repo
    app.dependency_overrides[get_projects_repository] = lambda: projects_repo
    app.dependency_overrides[get_stats_service] = stats_service_factory
    app.dependency_overrides[get_db_session] = test_db_session
    app.dependency_overrides[get_utc_now] = lambda: lambda: _FIXED_NOW

    async with AsyncClient(
        transport=ASGITransport(app=app, client=(client_ip, 12345)), base_url="http://test"
    ) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def client_ip(request) -> str:
    """Set the actual ASGI peer, optionally via indirect parametrization."""
    return getattr(request, "param", "198.51.100.42")


@pytest.fixture(autouse=True)
def reset_rate_limiter() -> Iterator[None]:
    """Keep IP buckets isolated without trusting forged forwarded headers."""
    limiter.reset()
    yield
    limiter.reset()
