"""Verified Meta AI collection rules."""

from src.news_sources.base import SourceProfile

PROFILE = SourceProfile(
    id='labs-meta',
    url='https://ai.meta.com/blog/',
    kind='html',
    # Featured badges share their URLs with headlines; dates belong to the card.
    config={
        'item_selector': 'div._amcy, div._amda',
        'title_selector': 'a._amd2, a._amdf',
        'link_selector': 'a._amd2, a._amdf',
        'date_selector': 'div._amun, div._amdc > div._amdj:last-child',
    },
    article_selectors=('._a5ci', '._a5cq', 'div._9bhp > p._a92o._a5c-._a5w7'),
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
