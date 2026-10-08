"""ORM models package: import everything so Base.metadata stays complete."""

from src.db.models.base import Base
from src.db.models.admin_sessions import AdminSession
from src.db.models.content_items import ContentItem
from src.db.models.page_views import PageView
from src.db.models.subscribers import Subscriber
from src.db.models.news_catalog import NewsCategory, NewsTopic
from src.db.models.news_sources import NewsSource
from src.db.models.news_items import NewsItem
from src.db.models.news_analyses import NewsAnalysis, NewsEditorialDecision
from src.db.models.news_jobs import NewsJob, NewsSourceRun
from src.db.models.news_settings import NewsSetting

__all__ = [
    "Base", "AdminSession", "ContentItem", "PageView", "Subscriber", "NewsCategory",
    "NewsTopic", "NewsSource", "NewsItem", "NewsAnalysis", "NewsEditorialDecision",
    "NewsJob", "NewsSourceRun", "NewsSetting",
]
