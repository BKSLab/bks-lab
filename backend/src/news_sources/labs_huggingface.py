"""Verified Hugging Face Blog collection rules."""

from src.news_sources.base import SourceProfile

PROFILE = SourceProfile(
    id='labs-huggingface',
    url='https://huggingface.co/blog/feed.xml',
    kind='rss',
    config={},
    article_selectors=('.blog-content',),
    publication_path_pattern='^/blog/.+',
    research_ids=('labs-huggingface',),
    slug='labs-huggingface',
    name='Hugging Face Blog',
    description='Open-weight модели, библиотеки, прикладные исследования',
    homepage_url='https://huggingface.co/blog',
    vendor_affiliated=True,
    priority=80,
    trust_score=80,
    fixture_path='tests/fixtures/news_sources/labs-huggingface.json',
    default_schedule={'mode': 'daily', 'times': ['08:00', '20:00']},
)
