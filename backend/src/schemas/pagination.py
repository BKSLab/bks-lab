"""Shared pagination schema for list endpoints (``Paged<T>``)."""

import math
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

ItemT = TypeVar("ItemT")


class Paged(BaseModel, Generic[ItemT]):
    """Paginated list response envelope."""

    items: list[ItemT] = Field(..., description="Items of the current page.")
    total: int = Field(..., description="Total number of items matching the filters.", examples=[42])
    page: int = Field(..., description="Current page number (1-based).", examples=[1])
    page_size: int = Field(..., description="Items per page.", examples=[10])
    pages: int = Field(..., description="Total number of pages.", examples=[5])

    @classmethod
    def build(
        cls, items: list[ItemT], total: int, page: int, page_size: int
    ) -> "Paged[ItemT]":
        """Build a response from a page slice and the total count."""
        pages = math.ceil(total / page_size) if total else 0
        return cls(items=items, total=total, page=page, page_size=page_size, pages=pages)
