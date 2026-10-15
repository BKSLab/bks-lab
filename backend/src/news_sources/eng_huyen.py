"""Verified Chip Huyen collection rules."""

from src.news_sources.base import SourceProfile

PROFILE = SourceProfile(
    id='eng-huyen',
    url='https://huyenchip.com/feed.xml',
    kind='rss',
    config={},
    article_selectors=('.post-content',),
    research_ids=('eng-huyen', 'authors-huyen'),
    slug='eng-huyen',
    name='Chip Huyen',
    description='AI Engineering, inference, ML-продукты и эксплуатация',
    homepage_url='https://huyenchip.com/blog/',
    vendor_affiliated=False,
    priority=80,
    trust_score=80,
    fixture_path='tests/fixtures/news_sources/eng-huyen.json',
    default_schedule={'mode': 'weekly', 'times': ['09:00'], 'weekdays': [0, 3]},
)
