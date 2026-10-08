"""Blog category schema and the fixed category set (design spec section 11)."""

from pydantic import BaseModel, Field

CATEGORY_TITLES: dict[str, str] = {
    "development": "Разработка",
    "ai": "AI",
    "management": "Управление",
    "thoughts": "Мысли",
    "accessibility": "Инклюзия",
}


class Category(BaseModel):
    """Blog category with the number of published articles."""

    slug: str = Field(..., description="Category slug used in URLs.", examples=["development"])
    title: str = Field(..., description="Human-readable category title.", examples=["Разработка"])
    articles_count: int = Field(..., ge=0, description="Number of published articles in the category.", examples=[12])
