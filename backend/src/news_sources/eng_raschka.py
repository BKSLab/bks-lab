"""Verified Sebastian Raschka collection rules."""

from src.news_sources.base import SourceProfile

PROFILE = SourceProfile(
    id='eng-raschka',
    url='https://sebastianraschka.com/rss_feed.xml',
    kind='rss',
    config={},
    article_selectors=('.post-content', '.entry-content', 'article'),
    research_ids=('eng-raschka', 'authors-raschka'),
    slug='eng-raschka',
    name='Sebastian Raschka',
    description='Устройство LLM, архитектуры, тренинг',
    homepage_url='https://sebastianraschka.com/blog/',
    vendor_affiliated=False,
    priority=60,
    trust_score=80,
    fixture_path='tests/fixtures/news_sources/eng-raschka.json',
    default_schedule={'mode': 'weekly', 'times': ['09:00'], 'weekdays': [0, 3]},
)
