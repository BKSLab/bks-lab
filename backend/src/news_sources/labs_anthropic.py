"""Verified Anthropic News collection rules."""

from src.news_sources.base import SourceProfile

PROFILE = SourceProfile(
    id='labs-anthropic',
    url='https://www.anthropic.com/news',
    kind='html',
    config={'item_selector': "main a:has(h2), main a:has(h3), main a[class*='PublicationList']", 'title_selector': 'h2, h3, [class*=title]', 'link_selector': ':scope'},
    article_selectors=('article article', "[class*='Body-module'][class*='body']"),
    publication_path_pattern='^/(?:news/|claude-)',
    slug='labs-anthropic',
    name='Anthropic News',
    description='Claude, работа агентов, safety, бизнес',
    homepage_url='https://www.anthropic.com/news',
    vendor_affiliated=True,
    priority=80,
    trust_score=80,
    fixture_path='tests/fixtures/news_sources/labs-anthropic.json',
    research_ids=('labs-anthropic',),
    default_schedule={'mode': 'daily', 'times': ['08:00', '20:00']},
)
