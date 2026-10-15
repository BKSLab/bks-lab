"""Synchronize supported source profiles and taxonomy: python -m scripts.seed_news."""

import asyncio
import sys
from collections.abc import Sequence

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.db.session import async_session_factory, engine
from src.exceptions.news import NewsRepositoryError
from src.repositories.news_catalog import NewsCatalogRepository
from src.news_sources import SourceProfile, get_source_profiles
from src.repositories.news_sources import NewsSourceRepository

CATEGORIES = [
    "AI Engineering / Разработка с ИИ",
    "Модели и исследования",
    "AI в бизнесе и B2B",
    "Корпоративные AI-системы и агенты",
    "Экономика и рынок труда",
    "Политика, право и регулирование",
    "Общество, культура и философия",
    "Безопасность, надёжность и этика",
    "Будущее AI и человека",
]
TOPICS = [
    "AI coding и агенты",
    "Оценивание LLM",
    "RAG в production",
    "Наблюдаемость LLM",
    "Prompt injection",
    "Архитектура AI-систем",
    "Открытые языковые модели",
    "AI в B2B",
    "Автоматизация процессов",
    "Экономика внедрения AI",
    "Human in the loop",
    "AI и рынок труда",
    "Регулирование AI",
    "Этика AI",
    "AI и философия сознания",
]


def load_source_profiles() -> tuple[SourceProfile, ...]:
    """Read the verified code registry without making network requests."""
    return get_source_profiles()


async def seed_news(
    session_factory: async_sessionmaker[AsyncSession],
    profiles: Sequence[SourceProfile],
) -> dict[str, int]:
    """Sync code-owned metadata, retaining user calendars, enablement and history."""
    for field in ("id", "slug", "url"):
        if len({getattr(profile, field) for profile in profiles}) != len(profiles):
            raise ValueError(f"Source profile {field} values must be unique")
    async with session_factory() as session:
        catalog = NewsCatalogRepository(session)
        categories = await catalog.seed(
            "categories",
            [{"name": name, "description": "", "active": True} for name in CATEGORIES],
        )
        topics = await catalog.seed(
            "topics",
            [{"name": name, "description": "", "active": True} for name in TOPICS],
        )
        sources = await NewsSourceRepository(session).synchronize_profiles([
            {
                "profile_id": profile.id, "slug": profile.slug,
                "name": profile.name, "description": profile.description,
                "url": profile.url, "kind": profile.kind, "config": profile.config,
                "priority": profile.priority, "trust_score": profile.trust_score,
                "vendor_affiliated": profile.vendor_affiliated,
                "schedule": profile.default_schedule,
            }
            for profile in profiles
        ])
    return {"sources": len(sources), "categories": categories, "topics": topics}


async def main() -> None:
    """Synchronize the supported registry and report taxonomy additions."""
    try:
        counts = await seed_news(async_session_factory, load_source_profiles())
        print(
            f"News seed synchronized: {counts['sources']} supported sources; "
            f"added {counts['categories']} categories, {counts['topics']} topics"
        )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (NewsRepositoryError, OSError, ValueError, ValidationError) as error:
        # Database and validation messages may include confidential connection data.
        print(f"News seed failed ({type(error).__name__})", file=sys.stderr)
        sys.exit(1)
