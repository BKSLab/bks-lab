"""Verified Код Дурова collection rules."""

from src.news_sources.base import SourceProfile

PROFILE = SourceProfile(
    id='ru-kod',
    slug='ru-kod',
    name='Код Дурова',
    description='Технологическая повестка и AI в продуктах',
    homepage_url='https://kod.ru/',
    url='https://kod.ru/rss',
    kind='rss',
    config={},
    article_selectors=('[class*="NewsDetail_content__"]',),
    publication_path_pattern='^/[a-z0-9][a-z0-9-]+',
    research_ids=('ru-kod',),
    vendor_affiliated=False,
    priority=60,
    trust_score=75,
    fixture_path='tests/fixtures/news_sources/ru-kod.json',
    default_schedule={'mode': 'daily', 'times': ['08:00', '14:00', '20:00']},
)
