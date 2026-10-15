"""Verified Meta AI collection rules."""

from src.news_sources.base import SourceProfile

PROFILE = SourceProfile(
    id='labs-meta',
    url='https://ai.meta.com/blog/',
    kind='html',
    config={'item_selector': "a._amcw[href*='/blog/']", 'title_selector': ':scope', 'link_selector': ':scope'},
    article_selectors=('._a5ci', '._a5cq'),
    publication_path_pattern='^/blog/.+',
    slug='labs-meta',
    name='Meta AI',
    description='Llama и исследования Meta',
    homepage_url='https://ai.meta.com/blog/',
    vendor_affiliated=True,
    priority=80,
    trust_score=80,
    fixture_path='tests/fixtures/news_sources/labs-meta.json',
    research_ids=('labs-meta',),
    default_schedule={'mode': 'daily', 'times': ['08:00', '20:00']},
)
