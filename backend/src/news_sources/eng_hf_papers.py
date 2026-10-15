"""Verified Hugging Face Papers collection rules."""

from src.news_sources.base import SourceProfile

PROFILE = SourceProfile(
    id='eng-hf-papers',
    url='https://huggingface.co/papers',
    kind='html',
    config={'item_selector': 'article:has(h3)', 'title_selector': 'h3', 'link_selector': "h3 a[href^='/papers/']"},
    article_selectors=("[data-target='PaperContent'] h2 + div",),
    publication_path_pattern='^/papers/\\d{4}\\.\\d+',
    slug='eng-hf-papers',
    name='Hugging Face Papers',
    description='Обзор новых научных работ',
    homepage_url='https://huggingface.co/papers',
    vendor_affiliated=True,
    priority=80,
    trust_score=80,
    fixture_path='tests/fixtures/news_sources/eng-hf-papers.json',
    research_ids=('eng-hf-papers',),
    default_schedule={'mode': 'daily', 'times': ['08:00', '20:00']},
)
