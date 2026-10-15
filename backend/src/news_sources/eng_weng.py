"""Verified Lilian Weng collection rules."""

from src.news_sources.base import SourceProfile

PROFILE = SourceProfile(
    id='eng-weng',
    url='https://lilianweng.github.io/index.xml',
    kind='rss',
    config={},
    article_selectors=('.post-content',),
    research_ids=('eng-weng', 'authors-weng'),
    slug='eng-weng',
    name='Lilian Weng',
    description='Глубокие технические обзоры LLM, агентов, RL',
    homepage_url='https://lilianweng.github.io/',
    vendor_affiliated=False,
    priority=80,
    trust_score=80,
    fixture_path='tests/fixtures/news_sources/eng-weng.json',
    default_schedule={'mode': 'weekly', 'times': ['09:00'], 'weekdays': [0, 3]},
)
