"""Service-to-endpoint wrapper for detail payloads that carry an ETag hash."""

from dataclasses import dataclass
from typing import Generic, TypeVar

PayloadT = TypeVar("PayloadT")


@dataclass(frozen=True)
class DetailResult(Generic[PayloadT]):
    """Detail payload plus the content hash used for the ETag header."""

    payload: PayloadT
    content_hash: str
