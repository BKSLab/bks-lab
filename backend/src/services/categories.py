"""Category use-cases: the fixed category set with article counts."""

from src.repositories.content_items import ContentItemRepository
from src.schemas.categories import CATEGORY_TITLES, Category


class CategoryService:
    """Use-cases for blog categories."""

    def __init__(self, articles_repository: ContentItemRepository):
        self.articles_repository = articles_repository

    async def list_categories(self) -> list[Category]:
        """Return all fixed categories with published-article counts.

        Categories with zero articles are included (blog filters need them).
        """
        items = await self.articles_repository.list_by_type(
            "article", statuses=("active", "archived")
        )
        counts: dict[str, int] = dict.fromkeys(CATEGORY_TITLES, 0)
        for item in items:
            if item.category in counts:
                counts[item.category] += 1
        return [
            Category(slug=slug, title=title, articles_count=counts[slug])
            for slug, title in CATEGORY_TITLES.items()
        ]
