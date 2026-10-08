"""Safe News Analyzer errors mapped by the existing application handlers."""

from src.exceptions.admin import ServiceError
from src.exceptions.repositories import RepositoryError


class NewsRepositoryError(RepositoryError):
    """News storage operation failed."""


class NewsConflictError(NewsRepositoryError):
    status_code = 409
    detail = "A conflicting news record already exists"


class NewsNotFoundError(ServiceError):
    status_code = 404
    detail = "News record not found"


class NewsValidationError(ServiceError):
    status_code = 422
    detail = "News configuration is invalid"


class NewsDiscoveryRequiredError(ServiceError):
    status_code = 409
    detail = "Complete discovery for this URL and configuration before saving"


class NewsLeaseLostError(NewsRepositoryError):
    """A stale worker must not commit any more stage output."""

    detail = "Job ownership expired"


class NewsSourceChangedError(NewsRepositoryError):
    """A source changed while an external request was in flight."""

    detail = "Source configuration changed during collection"
