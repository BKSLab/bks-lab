"""Storage repository exceptions."""

from fastapi import status


class RepositoryError(Exception):
    """Generic database failure inside a repository."""

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

    def __init__(self, error_details: str):
        self.error_details = error_details
        super().__init__(self.error_details)

    def __str__(self) -> str:
        return f"Repository error. Details: {self.error_details}"

    @property
    def detail(self) -> str:
        return "Database error. Please try again later."


class StatsRepositoryError(RepositoryError):
    """Failure in the stats (page views) repository."""


class ContentItemRepositoryError(RepositoryError):
    """Failure in the content_items projection repository."""


class ContentRepositoryError(RepositoryError):
    """Content directory or file could not be read safely."""

    @property
    def detail(self) -> str:
        return "Content storage error. Please try again later."


class AdminSessionRepositoryError(RepositoryError):
    """Session storage failed."""


class SubscriberRepositoryError(RepositoryError):
    """Subscriber storage failed."""
