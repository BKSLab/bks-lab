"""Verified METR collection rules."""

from src.news_sources.base import SourceProfile

PROFILE = SourceProfile(
    id='soc-metr',
    url='https://metr.org/',
    kind='html',
    config={'item_selector': '.featured-research-card:has(a[href^="/blog/"]), a.loc-feature[href^="/blog/"]', 'title_selector': 'h3'},
    article_selectors=('article .content', '.prose', '.post-content', 'article'),
    publication_path_pattern='^/blog/.+',
    slug='soc-metr',
    name='METR',
    description='Независимые измерения возможностей агентов и связанных рисков',
    homepage_url='https://metr.org/',
    vendor_affiliated=False,
    priority=80,
    trust_score=80,
    fixture_path='tests/fixtures/news_sources/soc-metr.json',
    research_ids=('soc-metr',),
    default_schedule={'mode': 'interval_days', 'times': ['09:00'], 'every_days': 3, 'start_date': '2026-01-01'},
)
