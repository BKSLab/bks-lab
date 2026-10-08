"""LLM request/content boundaries adapted from LLM_CLIENT_REFERENCE.md."""


class LlmClientRequestError(Exception):
    """One transport attempt failed; safe diagnostic only."""

    def __init__(self, message: str, *, retryable: bool = True) -> None:
        super().__init__(message)
        self.retryable = retryable


class LlmClientContentError(Exception):
    """One response is empty or fails JSON/schema validation."""


class LlmApiRequestError(Exception):
    """Final failure crossing the client/service boundary without provider data."""

    detail = "Не удалось выполнить AI-анализ. Материал сохранён для повторной обработки."

    def __init__(self, error_details: str = "LLM unavailable", *, retryable: bool = True) -> None:
        super().__init__(self.detail)
        self.error_details = error_details
        self.retryable = retryable
