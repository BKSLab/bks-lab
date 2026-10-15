"""Verified OECD AI Policy Observatory collection rules."""

from src.news_sources.base import SourceProfile

PROFILE = SourceProfile(
    id='soc-oecd',
    url='https://oecd.ai/en/wonk',
    kind='html',
    config={'item_selector': '.card--post', 'title_selector': '.card--post__content a', 'link_selector': 'a[href*="/wonk/"]'},
    article_selectors=('app-content-renderer .full-width',),
    publication_path_pattern='^/en/wonk/.+',
    slug='soc-oecd',
    name='OECD AI Policy Observatory',
    description='Международные политики, статистика, регулирование',
    homepage_url='https://oecd.ai/en/wonk',
    vendor_affiliated=False,
    priority=80,
    trust_score=80,
    fixture_path='tests/fixtures/news_sources/soc-oecd.json',
    research_ids=('soc-oecd',),
    default_schedule={'mode': 'interval_days', 'times': ['09:00'], 'every_days': 3, 'start_date': '2026-01-01'},
)
