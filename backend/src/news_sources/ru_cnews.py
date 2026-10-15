"""Verified CNews — Искусственный интеллект collection rules."""

from src.news_sources.base import SourceProfile

PROFILE = SourceProfile(
    id='ru-cnews',
    url='https://www.cnews.ru/inc/rss/biz.xml',
    kind='rss',
    config={},
    article_selectors=('.news_container',),
    publication_path_pattern='^/news/',
    slug='ru-cnews',
    name='CNews — Искусственный интеллект',
    description='Российский корпоративный IT и B2B-проекты',
    homepage_url='https://ai.cnews.ru/',
    vendor_affiliated=False,
    priority=60,
    trust_score=80,
    fixture_path='tests/fixtures/news_sources/ru-cnews.json',
    research_ids=('ru-cnews',),
    default_schedule={'mode': 'daily', 'times': ['08:00', '14:00', '20:00']},
)
