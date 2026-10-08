"""Expected use-case errors, translated only at the HTTP boundary."""


class ServiceError(Exception):
    status_code = 500
    detail = "Service unavailable"


class InvalidCredentialsError(ServiceError):
    status_code = 401
    detail = "Invalid credentials"


class NotAuthenticatedError(ServiceError):
    status_code = 401
    detail = "Not authenticated"


class AdminContentNotFoundError(ServiceError):
    status_code = 404
    detail = "Content not found"
