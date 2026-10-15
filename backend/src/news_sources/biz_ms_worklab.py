"""Verified Microsoft WorkLab collection rules."""

from src.news_sources.base import SourceProfile

PROFILE = SourceProfile(
    id='biz-ms-worklab',
    url='https://www.microsoft.com/en-us/worklab/',
    kind='html',
    config={'item_selector': "a[href*='/en-us/worklab/']:has(h3), a[href*='/en-us/worklab/']:has(h2)", 'title_selector': 'h2, h3', 'link_selector': ':scope'},
    article_selectors=('.wti2026-modular-custom-paragraph__body', '.podcast__rightside-content', '.article__main-content .generic-content__wrapper'),
    publication_path_pattern='^/en-us/worklab/.+',
    slug='biz-ms-worklab',
    name='Microsoft WorkLab',
    description='AI на рабочих местах и корпоративные процессы',
    homepage_url='https://www.microsoft.com/en-us/worklab/',
    vendor_affiliated=True,
    priority=80,
    trust_score=80,
    fixture_path='tests/fixtures/news_sources/biz-ms-worklab.json',
    research_ids=('biz-ms-worklab',),
    default_schedule={'mode': 'daily', 'times': ['08:00', '20:00']},
)
