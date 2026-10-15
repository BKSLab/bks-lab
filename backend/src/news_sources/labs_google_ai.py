"""Verified Google AI Blog collection rules."""

from src.news_sources.base import SourceProfile

PROFILE = SourceProfile(
    id='labs-google-ai',
    url='https://blog.google/innovation-and-ai/technology/ai/',
    kind='html',
    config={'item_selector': 'a.featured-article-cat-subcat-hero__link, a.uni-nup__article', 'title_selector': 'h2, h3', 'link_selector': ':scope'},
    article_selectors=('.uni-blog-article-container',),
    publication_path_pattern='^/innovation-and-ai/',
    slug='labs-google-ai',
    name='Google AI Blog',
    description='AI-продукты и широкий технологический контекст',
    homepage_url='https://blog.google/technology/ai/',
    vendor_affiliated=True,
    priority=80,
    trust_score=80,
    fixture_path='tests/fixtures/news_sources/labs-google-ai.json',
    research_ids=('labs-google-ai',),
    default_schedule={'mode': 'daily', 'times': ['08:00', '20:00']},
)
