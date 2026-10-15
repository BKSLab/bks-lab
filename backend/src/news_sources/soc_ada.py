"""Verified Ada Lovelace Institute collection rules."""

from src.news_sources.base import SourceProfile

PROFILE = SourceProfile(
    id='soc-ada',
    url='https://www.adalovelaceinstitute.org/',
    kind='html',
    config={'item_selector': 'article.c-card', 'title_selector': 'h3', 'link_selector': 'a.c-card__title'},
    article_selectors=('.c-text-block__content',),
    publication_path_pattern='^/(?:feature|policy-briefing|blog|report|news)/',
    slug='soc-ada',
    name='Ada Lovelace Institute',
    description='Общественный интерес, права, governance',
    homepage_url='https://www.adalovelaceinstitute.org/',
    vendor_affiliated=False,
    priority=80,
    trust_score=80,
    fixture_path='tests/fixtures/news_sources/soc-ada.json',
    research_ids=('soc-ada',),
    default_schedule={'mode': 'interval_days', 'times': ['09:00'], 'every_days': 3, 'start_date': '2026-01-01'},
)
