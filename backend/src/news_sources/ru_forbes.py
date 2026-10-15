"""Verified Forbes Russia collection rules."""

from src.news_sources.base import SourceProfile

PROFILE = SourceProfile(
    id='ru-forbes',
    url='https://www.forbes.ru/',
    kind='html',
    config={'item_selector': 'a._8ZT6F:has(p.uLUYv), a.QdliS:has(.Z7IxM)', 'title_selector': '.uLUYv, .Z7IxM', 'link_selector': ':scope'},
    article_selectors=('[itemprop~=articleBody]', '.article__text', '.article-body'),
    publication_path_pattern='^/[a-z-]+/\\d+-',
    slug='ru-forbes',
    name='Forbes Russia',
    description='Экономика и корпоративное внедрение',
    homepage_url='https://www.forbes.ru/',
    vendor_affiliated=False,
    priority=60,
    trust_score=80,
    fixture_path='tests/fixtures/news_sources/ru-forbes.json',
    research_ids=('ru-forbes',),
    default_schedule={'mode': 'daily', 'times': ['08:00', '14:00', '20:00']},
)
