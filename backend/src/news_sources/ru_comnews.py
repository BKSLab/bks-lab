"""Verified ComNews collection rules."""

from src.news_sources.base import SourceProfile

PROFILE = SourceProfile(
    id='ru-comnews',
    url='https://www.comnews.ru/',
    kind='html',
    config={'item_selector': '.block-node:has(a[href*="/content/"]), .news-item:has(a[href*="/content/"])', 'title_selector': 'h2, h3, .field-title, a[href*="/content/"]', 'link_selector': 'a[href*="/content/"]'},
    article_selectors=('.field-name-body',),
    publication_path_pattern='^/content/\\d+/',
    slug='ru-comnews',
    name='ComNews',
    description='Корпоративная цифровизация, инфраструктура, рынок',
    homepage_url='https://www.comnews.ru/',
    vendor_affiliated=False,
    priority=60,
    trust_score=80,
    fixture_path='tests/fixtures/news_sources/ru-comnews.json',
    research_ids=('ru-comnews',),
    default_schedule={'mode': 'daily', 'times': ['08:00', '14:00', '20:00']},
)
