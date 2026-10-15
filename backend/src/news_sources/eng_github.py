"""Verified GitHub Blog: AI collection rules."""

from src.news_sources.base import SourceProfile

PROFILE = SourceProfile(
    id='eng-github',
    url='https://github.blog/ai-and-ml/',
    kind='html',
    config={'item_selector': 'article.post-card', 'title_selector': 'h2, h3', 'link_selector': 'a.post-card__link'},
    article_selectors=('.post__content',),
    publication_path_pattern='^/ai-and-ml/.+',
    slug='eng-github',
    name='GitHub Blog: AI',
    description='AI coding, инструменты, workflow разработчиков',
    homepage_url='https://github.blog/ai-and-ml/',
    vendor_affiliated=True,
    priority=60,
    trust_score=80,
    fixture_path='tests/fixtures/news_sources/eng-github.json',
    research_ids=('eng-github',),
    default_schedule={'mode': 'daily', 'times': ['08:00', '20:00']},
)
