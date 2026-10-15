"""Verified Noema Magazine collection rules."""

from src.news_sources.base import SourceProfile

PROFILE = SourceProfile(
    id='soc-noema',
    url='https://www.noemamag.com/?feed=noemarss',
    kind='rss',
    config={},
    article_selectors=('.entry-content', '.article-body', 'article'),
    publication_path_pattern='^/[^/]+',
    slug='soc-noema',
    name='Noema Magazine',
    description='Философия, культура, технологии и будущее общества',
    homepage_url='https://www.noemamag.com/',
    vendor_affiliated=False,
    priority=60,
    trust_score=80,
    fixture_path='tests/fixtures/news_sources/soc-noema.json',
    research_ids=('soc-noema',),
    default_schedule={'mode': 'daily', 'times': ['08:00', '20:00']},
)
