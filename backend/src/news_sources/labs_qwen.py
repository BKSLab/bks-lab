"""Verified Qwen collection rules."""

from src.news_sources.base import SourceProfile

PROFILE = SourceProfile(
    id='labs-qwen',
    url='https://qwenlm.github.io/',
    kind='html',
    config={'item_selector': 'article.post-entry', 'title_selector': 'h2', 'link_selector': 'a.entry-link'},
    article_selectors=('.post-content',),
    publication_path_pattern='^/blog/.+',
    slug='labs-qwen',
    name='Qwen',
    description='Открытые модели и технические релизы',
    homepage_url='https://qwenlm.github.io/',
    vendor_affiliated=True,
    priority=60,
    trust_score=80,
    fixture_path='tests/fixtures/news_sources/labs-qwen.json',
    research_ids=('labs-qwen',),
    default_schedule={'mode': 'daily', 'times': ['08:00', '20:00']},
)
