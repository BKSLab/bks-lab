"""Verified Хабр — Искусственный интеллект collection rules."""

from src.news_sources.base import SourceProfile

PROFILE = SourceProfile(
    id='ru-habr-ai',
    url='https://habr.com/ru/rss/hubs/artificial_intelligence/articles/?fl=ru',
    kind='rss',
    config={},
    article_selectors=('.article-formatted-body',),
    publication_path_pattern='^/ru/(?:companies/[^/]+/)?(?:articles|news)/\\d+/',
    slug='ru-habr-ai',
    name='Хабр — Искусственный интеллект',
    description='Кейсы, переводы, инженерная практика',
    homepage_url='https://habr.com/ru/hubs/artificial_intelligence/',
    vendor_affiliated=False,
    priority=80,
    trust_score=80,
    fixture_path='tests/fixtures/news_sources/ru-habr-ai.json',
    research_ids=('ru-habr-ai',),
    default_schedule={'mode': 'daily', 'times': ['08:00', '14:00', '20:00']},
)
