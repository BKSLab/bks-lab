"""Verified Ethan Mollick / One Useful Thing collection rules."""

from src.news_sources.base import SourceProfile

PROFILE = SourceProfile(
    id='biz-mollick',
    url='https://www.oneusefulthing.org/feed',
    kind='rss',
    config={},
    article_selectors=('.body.markup', '.available-content'),
    research_ids=('biz-mollick', 'authors-mollick'),
    slug='biz-mollick',
    name='Ethan Mollick / One Useful Thing',
    description='Как AI влияет на труд, обучение, организации и управление',
    homepage_url='https://www.oneusefulthing.org/',
    vendor_affiliated=False,
    priority=80,
    trust_score=80,
    fixture_path='tests/fixtures/news_sources/biz-mollick.json',
    default_schedule={'mode': 'weekly', 'times': ['09:00'], 'weekdays': [0, 3]},
)
