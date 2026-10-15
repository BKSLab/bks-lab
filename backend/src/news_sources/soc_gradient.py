"""Verified The Gradient collection rules."""

from src.news_sources.base import SourceProfile

PROFILE = SourceProfile(
    id='soc-gradient',
    url='https://thegradient.pub/rss/',
    kind='rss',
    config={},
    article_selectors=('.c-content',),
    publication_path_pattern='^/[^/]+/',
    slug='soc-gradient',
    name='The Gradient',
    description='Глубокие эссе об исследованиях и последствиях AI',
    homepage_url='https://thegradient.pub/',
    vendor_affiliated=False,
    priority=60,
    trust_score=80,
    fixture_path='tests/fixtures/news_sources/soc-gradient.json',
    research_ids=('soc-gradient',),
    default_schedule={'mode': 'daily', 'times': ['08:00', '20:00']},
)
