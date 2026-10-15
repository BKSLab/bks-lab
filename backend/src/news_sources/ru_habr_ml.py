"""Verified Хабр — Машинное обучение collection rules."""

from src.news_sources.base import SourceProfile

PROFILE = SourceProfile(
    id='ru-habr-ml',
    url='https://habr.com/ru/rss/hubs/machine_learning/articles/?fl=ru',
    kind='rss',
    config={},
    article_selectors=('.article-formatted-body',),
    publication_path_pattern='^/ru/(?:companies/[^/]+/)?(?:articles|news)/\\d+/',
    slug='ru-habr-ml',
    name='Хабр — Машинное обучение',
    description='ML, LLM, внедрение, инструменты',
    homepage_url='https://habr.com/ru/hubs/machine_learning/',
    vendor_affiliated=False,
    priority=80,
    trust_score=80,
    fixture_path='tests/fixtures/news_sources/ru-habr-ml.json',
    research_ids=('ru-habr-ml',),
    default_schedule={'mode': 'daily', 'times': ['08:00', '14:00', '20:00']},
)
