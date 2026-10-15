"""Verified Partnership on AI collection rules."""

from src.news_sources.base import SourceProfile

PROFILE = SourceProfile(
    id='soc-partnership',
    url='https://partnershiponai.org/',
    kind='html',
    config={'item_selector': 'a.post-card[href^="https://partnershiponai.org/"]', 'title_selector': '.content_block', 'link_selector': ':scope'},
    article_selectors=('.entry-content', '.post-content', '.article-content'),
    publication_path_pattern='^/(?!wp-content/)[a-z0-9-]+/',
    slug='soc-partnership',
    name='Partnership on AI',
    description='Ответственные практики AI и governance',
    homepage_url='https://partnershiponai.org/',
    vendor_affiliated=False,
    priority=60,
    trust_score=80,
    fixture_path='tests/fixtures/news_sources/soc-partnership.json',
    research_ids=('soc-partnership',),
    default_schedule={'mode': 'interval_days', 'times': ['09:00'], 'every_days': 3, 'start_date': '2026-01-01'},
)
