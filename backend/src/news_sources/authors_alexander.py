"""Verified Scott Alexander collection rules."""

from src.news_sources.base import SourceProfile

PROFILE = SourceProfile(
    id='authors-alexander',
    url='https://www.astralcodexten.com/feed',
    kind='rss',
    config={},
    article_selectors=('.body.markup', '.available-content'),
    publication_path_pattern='^/p/.+',
    slug='authors-alexander',
    name='Scott Alexander',
    description='Аналитические эссе, политическая философия и AI',
    homepage_url='https://www.astralcodexten.com/',
    vendor_affiliated=False,
    priority=60,
    trust_score=80,
    fixture_path='tests/fixtures/news_sources/authors-alexander.json',
    research_ids=('authors-alexander',),
    default_schedule={'mode': 'weekly', 'times': ['09:00'], 'weekdays': [0, 3]},
)
