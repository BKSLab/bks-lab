"""Verified AI Now Institute collection rules."""

from src.news_sources.base import SourceProfile

PROFILE = SourceProfile(
    id='soc-ai-now',
    url='https://ainowinstitute.org/',
    kind='html',
    config={'item_selector': "a[href*='/publications/']:has(h2), a[href*='/publications/']:has(h3), a.d-flex[href*='/publications/']", 'title_selector': 'h2, h3, :scope', 'link_selector': ':scope'},
    article_selectors=('main.entry-content', 'main .entry-content'),
    publication_path_pattern='^/publications/.+',
    slug='soc-ai-now',
    name='AI Now Institute',
    description='Власть, труд, корпоративное влияние, социальные последствия',
    homepage_url='https://ainowinstitute.org/',
    vendor_affiliated=False,
    priority=80,
    trust_score=80,
    fixture_path='tests/fixtures/news_sources/soc-ai-now.json',
    research_ids=('soc-ai-now',),
    default_schedule={'mode': 'interval_days', 'times': ['09:00'], 'every_days': 3, 'start_date': '2026-01-01'},
)
