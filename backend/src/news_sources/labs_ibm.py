"""Verified IBM Research AI collection rules."""

from src.news_sources.base import SourceProfile

PROFILE = SourceProfile(
    id='labs-ibm',
    url='https://research.ibm.com/rss',
    kind='rss',
    config={},
    article_selectors=('.nEgU0',),
    publication_path_pattern='^/blog/.+',
    slug='labs-ibm',
    name='IBM Research AI',
    description='Enterprise AI, governance, научные разработки',
    homepage_url='https://research.ibm.com/artificial-intelligence',
    vendor_affiliated=True,
    priority=60,
    trust_score=80,
    fixture_path='tests/fixtures/news_sources/labs-ibm.json',
    research_ids=('labs-ibm',),
    default_schedule={'mode': 'daily', 'times': ['08:00', '20:00']},
)
