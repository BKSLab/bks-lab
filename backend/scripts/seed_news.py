"""Seed missing source suggestions and taxonomy: python -m scripts.seed_news."""

import asyncio
import json
import sys
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.db.session import async_session_factory, engine
from src.exceptions.news import NewsRepositoryError
from src.repositories.news_catalog import NewsCatalogRepository
from src.repositories.news_source_catalogue import NewsSourceCatalogueRepository
from src.schemas.news_source_catalogue import SourceCatalogueEntry

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


def load_source_catalogue() -> list[SourceCatalogueEntry]:
    """Validate bundled seed data before any database writes."""
    path = Path(__file__).resolve().parents[1] / "src/data/news_source_catalogue.json"
    entries = [
        SourceCatalogueEntry.model_validate(entry)
        for entry in json.loads(path.read_text(encoding="utf-8"))
    ]
    if len({entry.id for entry in entries}) != len(entries):
        raise ValueError("Source catalogue IDs must be unique")
    return entries


async def seed_news(
    session_factory: async_sessionmaker[AsyncSession],
    entries: list[SourceCatalogueEntry],
) -> dict[str, int]:
    """Insert missing defaults, preserving catalogue edits and connected sources."""
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
        suggestions = await NewsSourceCatalogueRepository(session).seed([
            {
                "id": entry.id, "position": position,
                "data": entry.model_dump(by_alias=True),
            }
            for position, entry in enumerate(entries)
        ])
    return {"catalogue": suggestions, "categories": categories, "topics": topics}


async def main() -> None:
    """Fill only missing rows at startup and report insertion counts."""
    try:
        counts = await seed_news(async_session_factory, load_source_catalogue())
        print(
            "News seed added: "
            f"{counts['catalogue']} catalogue entries, "
            f"{counts['categories']} categories, {counts['topics']} topics"
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
