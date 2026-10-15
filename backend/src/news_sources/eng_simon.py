"""Verified Simon Willison collection rules."""

from src.news_sources.base import SourceProfile

PROFILE = SourceProfile(
    id='eng-simon',
    url='https://simonwillison.net/atom/entries/',
    kind='rss',
    config={},
    article_selectors=('.entryPage > div',),
    research_ids=('eng-simon', 'authors-simon'),
    slug='eng-simon',
    name='Simon Willison',
    description='Практика LLM, prompt injection, инструменты, оценка моделей, разработка',
    homepage_url='https://simonwillison.net/',
    vendor_affiliated=False,
    priority=80,
    trust_score=80,
    fixture_path='tests/fixtures/news_sources/eng-simon.json',
    default_schedule={'mode': 'daily', 'times': ['08:00', '20:00']},
)
