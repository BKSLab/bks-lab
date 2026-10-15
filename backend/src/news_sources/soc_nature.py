"""Verified Nature Machine Intelligence collection rules."""

from src.news_sources.base import SourceProfile

PROFILE = SourceProfile(
    id='soc-nature',
    url='https://www.nature.com/natmachintell.rss',
    kind='rss',
    config={},
    article_selectors=('.c-article-body', '.c-article-section__content'),
    publication_path_pattern='^/articles/.+',
    slug='soc-nature',
    name='Nature Machine Intelligence',
    description='Научная перспектива, этика, обществознание',
    homepage_url='https://www.nature.com/natmachintell/',
    vendor_affiliated=False,
    priority=60,
    trust_score=80,
    fixture_path='tests/fixtures/news_sources/soc-nature.json',
    research_ids=('soc-nature',),
    default_schedule={'mode': 'daily', 'times': ['08:00', '20:00']},
)
