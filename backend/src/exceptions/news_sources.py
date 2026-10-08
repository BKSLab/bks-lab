"""Safe errors from external news sources; never include response bodies."""


class NewsSourceError(Exception):
    """Expected fetch/parser failure suitable for a source run record."""

    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class UnsafeNewsUrlError(NewsSourceError):
    def __init__(self) -> None:
        super().__init__("unsafe_url", "Разрешены только публичные HTTP/HTTPS-адреса без пароля.")


class NewsRobotsError(NewsSourceError):
    def __init__(self) -> None:
        super().__init__("robots_denied", "Правила robots.txt запрещают получение этой страницы.")
