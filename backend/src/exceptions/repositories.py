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
    """Failure in the content_items storage repository."""


class ContentItemConflictError(ContentItemRepositoryError):
    """A content item with the same (type, slug) already exists."""

    status_code = status.HTTP_409_CONFLICT

    @property
    def detail(self) -> str:
        return "A material with this slug already exists."


class ContentRevisionRepositoryError(RepositoryError):
    """Failure in the content_revisions storage repository."""


class ContentRevisionConflictError(ContentRevisionRepositoryError):
    """A revision with the same (item_id, revision_no) already exists."""

    status_code = status.HTTP_409_CONFLICT

    @property
    def detail(self) -> str:
        return "A conflicting content revision already exists."


class AdminSessionRepositoryError(RepositoryError):
    """Session storage failed."""


class SubscriberRepositoryError(RepositoryError):
    """Subscriber storage failed."""


class FeedbackRepositoryError(RepositoryError):
    """Feedback storage failed."""


class MediaFileRepositoryError(RepositoryError):
    """Failure in the media_files storage repository."""
