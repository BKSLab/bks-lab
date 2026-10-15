"""Request-scoped repositories and News Analyzer use cases."""

from typing import Annotated

from fastapi import Depends

from src.core.settings import get_settings
from src.dependencies.db_session import DbSessionDep
from src.repositories.news_analyses import NewsAnalysisRepository
from src.repositories.news_catalog import NewsCatalogRepository
from src.repositories.news_decisions import NewsDecisionRepository
from src.repositories.news_items import NewsItemRepository
from src.repositories.news_jobs import NewsJobRepository
from src.repositories.news_runs import NewsRunRepository
from src.repositories.news_settings import NewsSettingsRepository
from src.repositories.news_sources import NewsSourceRepository
from src.services.news_admin import NewsAdminService


def get_news_sources(session: DbSessionDep) -> NewsSourceRepository:
    return NewsSourceRepository(session)


def get_news_catalog(session: DbSessionDep) -> NewsCatalogRepository:
    return NewsCatalogRepository(session)


def get_news_items(session: DbSessionDep) -> NewsItemRepository:
    return NewsItemRepository(session)


def get_news_analyses(session: DbSessionDep) -> NewsAnalysisRepository:
    return NewsAnalysisRepository(session)


def get_news_decisions(session: DbSessionDep) -> NewsDecisionRepository:
    return NewsDecisionRepository(session)


def get_news_jobs(session: DbSessionDep) -> NewsJobRepository:
    return NewsJobRepository(session)


def get_news_runs(session: DbSessionDep) -> NewsRunRepository:
    return NewsRunRepository(session)


def get_news_settings(session: DbSessionDep) -> NewsSettingsRepository:
    return NewsSettingsRepository(session)


SourcesDep = Annotated[NewsSourceRepository, Depends(get_news_sources)]
CatalogDep = Annotated[NewsCatalogRepository, Depends(get_news_catalog)]
ItemsDep = Annotated[NewsItemRepository, Depends(get_news_items)]
AnalysesDep = Annotated[NewsAnalysisRepository, Depends(get_news_analyses)]
DecisionsDep = Annotated[NewsDecisionRepository, Depends(get_news_decisions)]
JobsDep = Annotated[NewsJobRepository, Depends(get_news_jobs)]
RunsDep = Annotated[NewsRunRepository, Depends(get_news_runs)]
SettingsDep = Annotated[NewsSettingsRepository, Depends(get_news_settings)]


def get_news_admin_service(
    sources: SourcesDep,
    catalog: CatalogDep,
    items: ItemsDep,
    analyses: AnalysesDep,
    decisions: DecisionsDep,
    jobs: JobsDep,
    runs: RunsDep,
    settings: SettingsDep,
) -> NewsAdminService:
    """Construct the editorial service without network or scheduler dependencies."""
    return NewsAdminService(
        sources=sources,
        catalog=catalog,
        items=items,
        analyses=analyses,
        decisions=decisions,
        jobs=jobs,
        runs=runs,
        settings=settings,
        config=get_settings().news,
    )


NewsAdminServiceDep = Annotated[NewsAdminService, Depends(get_news_admin_service)]
