"""Verified NVIDIA AI Blog collection rules."""

from src.news_sources.base import SourceProfile

PROFILE = SourceProfile(
    id='labs-nvidia',
    url='https://blogs.nvidia.com/blog/tag/artificial-intelligence/feed/',
    kind='rss',
    config={},
    article_selectors=('.entry-content', '.post-content'),
    publication_path_pattern='^/blog/.+',
    slug='labs-nvidia',
    name='NVIDIA AI Blog',
    description='Инфраструктура, inference, бизнес-кейсы',
    homepage_url='https://blogs.nvidia.com/blog/tag/artificial-intelligence/',
    vendor_affiliated=True,
    priority=60,
    trust_score=80,
    fixture_path='tests/fixtures/news_sources/labs-nvidia.json',
    research_ids=('labs-nvidia',),
    default_schedule={'mode': 'daily', 'times': ['08:00', '20:00']},
)
