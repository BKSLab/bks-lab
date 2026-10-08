"""Small news fixtures shared by PostgreSQL and protected API tests."""

from hashlib import sha256

from src.repositories.news_sources import NewsSourceRepository


async def add_source(session, name="Example", url="https://example.org/feed.xml"):
    return await NewsSourceRepository(session).create(
        {
            "name": name,
            "url": url,
            "kind": "rss",
            "config": {},
            "topic_ids": [],
            "category_ids": [],
            "active": True,
        }
    )


def collected(
    *,
    external_id="one",
    url="https://example.org/one",
    title="Original title",
    content="Source content",
):
    return {
        "external_id": external_id,
        "url": url,
        "canonical_url": url,
        "normalized_url": url,
        "title": title,
        "excerpt": content,
        "content": content,
        "content_hash": sha256(f"{title}:{content}".encode()).hexdigest(),
        "metadata_json": {},
        "published_at": None,
        "updated_at": None,
    }


def analysis_data(*, category_id=None, topic_ids=None):
    return {
        "is_relevant": True,
        "category_id": category_id,
        "topic_ids": topic_ids or [],
        "suggested_topics": [],
        "scores": {
            "topical_fit": 80,
            "significance": 70,
            "freshness": 60,
            "article_potential": 90,
        },
        "summary_ru": "Краткая аннотация.",
        "editorial_comment_ru": "Подходит для разбора.",
        "recommended_formats": ["longread_candidate", "short_news_candidate"],
        "confidence": 0.8,
        "needs_verification": True,
        "news_score": 73.5,
        "article_score": 78.5,
    }
