"""Verified Hamel Husain collection rules."""

from src.news_sources.base import SourceProfile

PROFILE = SourceProfile(
    id='eng-hamel',
    url='https://hamel.dev/index.xml',
    kind='rss',
    config={},
    article_selectors=('main.content', '#quarto-document-content'),
    publication_path_pattern='^/blog/posts/.+',
    slug='eng-hamel',
    name='Hamel Husain',
    description='AI-оценивание, прикладная инженерия, обучение',
    homepage_url='https://hamel.dev/',
    vendor_affiliated=False,
    priority=60,
    trust_score=80,
    fixture_path='tests/fixtures/news_sources/eng-hamel.json',
    research_ids=('eng-hamel',),
    default_schedule={'mode': 'weekly', 'times': ['09:00'], 'weekdays': [0, 3]},
)
