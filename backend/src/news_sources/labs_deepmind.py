"""Verified Google DeepMind collection rules."""

from src.news_sources.base import SourceProfile

PROFILE = SourceProfile(
    id='labs-deepmind',
    url='https://deepmind.google/blog/',
    kind='html',
    config={'item_selector': '.card:has(h3), .card:has(h2)', 'title_selector': 'h2, h3', 'link_selector': 'a[href]'},
    article_selectors=('.uni-blog-article-container', '.blog-article-container', 'main .rich-text'),
    publication_path_pattern='/(?:blog|innovation-and-ai)/',
    slug='labs-deepmind',
    name='Google DeepMind',
    description='Научные работы, модели, исследования',
    homepage_url='https://deepmind.google/discover/blog/',
    vendor_affiliated=True,
    priority=80,
    trust_score=80,
    fixture_path='tests/fixtures/news_sources/labs-deepmind.json',
    research_ids=('labs-deepmind',),
    default_schedule={'mode': 'daily', 'times': ['08:00', '20:00']},
)
