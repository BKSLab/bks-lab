"""Verified РБК Тренды collection rules."""

from src.news_sources.base import SourceProfile

PROFILE = SourceProfile(
    id='ru-rbc',
    url='https://trends.rbc.ru/trends/',
    kind='html',
    config={'item_selector': 'a.g-inline-text-badges.js-item-link', 'title_selector': '.g-inline-text-badges__text', 'link_selector': ':scope'},
    article_selectors=('.article__text', '.article__content', '.article__text__overview'),
    publication_path_pattern='^/trends/[^/]+/[a-z0-9]+',
    slug='ru-rbc',
    name='РБК Тренды',
    description='AI, экономика, общество, будущее профессий',
    homepage_url='https://trends.rbc.ru/',
    vendor_affiliated=False,
    priority=60,
    trust_score=80,
    fixture_path='tests/fixtures/news_sources/ru-rbc.json',
    research_ids=('ru-rbc',),
    default_schedule={'mode': 'daily', 'times': ['08:00', '14:00', '20:00']},
)
