"""Feedback delivery errors without message bodies or SMTP credentials."""

from src.exceptions.admin import ServiceError


class MailDeliveryError(Exception):
    """The SMTP client could not deliver a message."""


class FeedbackUnavailableError(ServiceError):
    status_code = 503
    detail = "Feedback delivery is temporarily unavailable"
