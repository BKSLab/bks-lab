"""Verified Microsoft Research collection rules."""

from src.news_sources.base import SourceProfile

PROFILE = SourceProfile(
    id='labs-ms-research',
    url='https://www.microsoft.com/en-us/research/feed/',
    kind='rss',
    config={},
    article_selectors=('.single-post__content', '.entry-content', '.podcast__rightside-content'),
    publication_path_pattern='^/en-us/research/(?:blog|podcast)/',
    slug='labs-ms-research',
    name='Microsoft Research',
    description='Корпоративные исследования, агенты, качество систем',
    homepage_url='https://www.microsoft.com/en-us/research/blog/',
    vendor_affiliated=True,
    priority=80,
    trust_score=80,
    fixture_path='tests/fixtures/news_sources/labs-ms-research.json',
    research_ids=('labs-ms-research',),
    default_schedule={'mode': 'daily', 'times': ['08:00', '20:00']},
)
