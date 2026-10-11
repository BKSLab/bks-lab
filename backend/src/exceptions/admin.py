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


class ContentValidationError(ServiceError):
    status_code = 422
    detail = "Content data is invalid for its type"


class AdMarkerError(ServiceError):
    status_code = 422
    detail = "Ad markers are only allowed in articles: at most two, never the first or last block"


class MediaValidationError(ServiceError):
    status_code = 422
    detail = "Unsupported image: only JPEG, PNG or WebP within the size limit"


class MediaFileTooLargeError(ServiceError):
    status_code = 413
    detail = "Image exceeds the upload size limit"
