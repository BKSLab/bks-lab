"""Verified Горький collection rules."""

from src.news_sources.base import SourceProfile

PROFILE = SourceProfile(
    id='ru-gorky',
    url='https://gorky.media/',
    kind='html',
    config={'item_selector': 'a[href*="/fragments/"]:has(h2), a[href*="/context/"]:has(h2), a[href*="/reviews/"]:has(h2), a[href*="/fragments/"]:has(h3), a[href*="/context/"]:has(h3), a[href*="/reviews/"]:has(h3)', 'title_selector': 'h2, h3', 'link_selector': ':scope'},
    article_selectors=('.publication-content',),
    publication_path_pattern='^/(?:fragments|context|reviews)/.+',
    slug='ru-gorky',
    name='Горький',
    description='Культурно-философская перспектива, не ежедневные AI-новости',
    homepage_url='https://gorky.media/',
    vendor_affiliated=False,
    priority=60,
    trust_score=80,
    fixture_path='tests/fixtures/news_sources/ru-gorky.json',
    research_ids=('ru-gorky',),
    default_schedule={'mode': 'daily', 'times': ['08:00', '14:00', '20:00']},
)
