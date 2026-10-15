"""Verified arXiv cs.CL collection rules."""

from src.news_sources.base import SourceProfile

PROFILE = SourceProfile(
    id='eng-arxiv-cl',
    url='https://rss.arxiv.org/rss/cs.CL',
    kind='rss',
    config={},
    article_selectors=('blockquote.abstract',),
    publication_path_pattern='^/abs/\\d{4}\\.\\d+',
    slug='eng-arxiv-cl',
    name='arXiv cs.CL',
    description='LLM, NLP, reasoning',
    homepage_url='https://arxiv.org/list/cs.CL/recent',
    vendor_affiliated=False,
    priority=80,
    trust_score=80,
    fixture_path='tests/fixtures/news_sources/eng-arxiv-cl.json',
    research_ids=('eng-arxiv-cl',),
    default_schedule={'mode': 'daily', 'times': ['08:00', '20:00']},
)
