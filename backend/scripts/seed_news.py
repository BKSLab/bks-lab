"""Seed missing editorial taxonomy: python -m scripts.seed_news."""

import asyncio

from src.db.session import async_session_factory, engine
from src.repositories.news_catalog import NewsCatalogRepository

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


async def seed_news() -> None:
    """Insert catalog defaults without enabling sources or overwriting editor changes."""
    async with async_session_factory() as session:
        catalog = NewsCatalogRepository(session)
        await catalog.seed(
            "categories",
            [{"name": name, "description": "", "active": True} for name in CATEGORIES],
        )
        await catalog.seed(
            "topics",
            [{"name": name, "description": "", "active": True} for name in TOPICS],
        )
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_news())
