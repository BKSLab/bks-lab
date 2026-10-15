"""Verified Tproger collection rules."""

from src.news_sources.base import SourceProfile

PROFILE = SourceProfile(
    id='ru-tproger',
    url='https://tproger.ru/feed',
    kind='rss',
    config={},
    article_selectors=('.tp-content-viewer',),
    publication_path_pattern='^/(?:articles|news)/',
    slug='ru-tproger',
    name='Tproger',
    description='Прикладная разработка, инструменты, оперативные темы',
    homepage_url='https://tproger.ru/',
    vendor_affiliated=False,
    priority=80,
    trust_score=80,
    fixture_path='tests/fixtures/news_sources/ru-tproger.json',
    research_ids=('ru-tproger',),
    default_schedule={'mode': 'daily', 'times': ['08:00', '14:00', '20:00']},
)
