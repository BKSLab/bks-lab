"""Public feedback errors without message bodies or database diagnostics."""

from src.exceptions.admin import ServiceError


class FeedbackUnavailableError(ServiceError):
    status_code = 503
    detail = "Feedback storage is temporarily unavailable"
