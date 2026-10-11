"""Unit tests for ProjectService with a mocked repository."""

from unittest.mock import AsyncMock

import pytest

from src.exceptions.content import ProjectNotFoundError
from src.repositories.content_items import ContentItemRepository
from src.services.projects import ProjectService
from tests.helpers import make_project_item


def make_service(items: list) -> ProjectService:
    repository = AsyncMock(spec=ContentItemRepository)
    repository.list_by_type.side_effect = lambda content_type, statuses=None: [
        item for item in items
        if item.type == content_type and (statuses is None or item.status in statuses)
    ]
    repository.get_by_slug.side_effect = lambda content_type, slug: next(
        (item for item in items if item.type == content_type and item.slug == slug), None
    )
    return ProjectService(projects_repository=repository)


PROJECTS = [
    make_project_item("second", order=2),
    make_project_item("first", featured=True, order=1),
    make_project_item("archived-one", project_status="archived", order=3),
    make_project_item("draft-one", draft=True, order=0),
]


async def test_list_projects_excludes_drafts_and_sorts_by_order() -> None:
    service = make_service(PROJECTS)

    result = await service.list_projects(featured=None)

    assert [item.slug for item in result] == ["first", "second", "archived-one"]
    assert result[2].status == "archived"


async def test_list_projects_filters_featured() -> None:
    service = make_service(PROJECTS)

    featured = await service.list_projects(featured=True)
    not_featured = await service.list_projects(featured=False)

    assert [item.slug for item in featured] == ["first"]
    assert [item.slug for item in not_featured] == ["second", "archived-one"]


async def test_get_project_returns_archived_but_not_draft() -> None:
    service = make_service(PROJECTS)

    archived = await service.get_project(slug="archived-one")

    assert archived.payload.status == "archived"
    assert archived.content_hash
    with pytest.raises(ProjectNotFoundError) as draft:
        await service.get_project(slug="draft-one")
    with pytest.raises(ProjectNotFoundError) as missing:
        await service.get_project(slug="nope")

    assert draft.value.status_code == 404
    assert missing.value.status_code == 404
