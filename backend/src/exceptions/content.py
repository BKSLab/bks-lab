"""Content-related domain exceptions."""

from fastapi import status


class ArticleNotFoundError(Exception):
    """Article is missing or not public (draft)."""

    status_code = status.HTTP_404_NOT_FOUND

    def __init__(self, slug: str):
        self.slug = slug
        super().__init__(self.slug)

    def __str__(self) -> str:
        return f"Article not found: {self.slug}"

    @property
    def detail(self) -> str:
        return f"Article not found: {self.slug}"


class ProjectNotFoundError(Exception):
    """Project is missing or not public (draft)."""

    status_code = status.HTTP_404_NOT_FOUND

    def __init__(self, slug: str):
        self.slug = slug
        super().__init__(self.slug)

    def __str__(self) -> str:
        return f"Project not found: {self.slug}"

    @property
    def detail(self) -> str:
        return f"Project not found: {self.slug}"
