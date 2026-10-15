"""Verified Mistral AI News collection rules."""

from src.news_sources.base import SourceProfile

PROFILE = SourceProfile(
    id='labs-mistral',
    url='https://mistral.ai/news/rss',
    kind='rss',
    config={},
    article_selectors=('[class*=rich-text]', 'article'),
    publication_path_pattern='^/news/.+',
    slug='labs-mistral',
    name='Mistral AI News',
    description='Европейские модели, open-weight и enterprise',
    homepage_url='https://mistral.ai/news',
    vendor_affiliated=True,
    priority=80,
    trust_score=80,
    fixture_path='tests/fixtures/news_sources/labs-mistral.json',
    research_ids=('labs-mistral',),
    default_schedule={'mode': 'daily', 'times': ['08:00', '20:00']},
)
