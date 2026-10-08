"""Category use-cases: the fixed category set with article counts."""

from typing import cast

from src.repositories.markdown_content import MarkdownContentRepository
from src.schemas.categories import CATEGORY_TITLES, Category
from src.schemas.frontmatter import ArticleFrontmatter


class CategoryService:
    """Use-cases for blog categories."""

    def __init__(self, articles_repository: MarkdownContentRepository):
        self.articles_repository = articles_repository

    async def list_categories(self) -> list[Category]:
        """Return all fixed categories with published-article counts.

        Categories with zero articles are included (blog filters need them).
        """
        items = await self.articles_repository.get_all()
        counts: dict[str, int] = dict.fromkeys(CATEGORY_TITLES, 0)
        for item in items:
            if item.status == "draft":
                continue
            category = cast(ArticleFrontmatter, item.frontmatter).category
            if category in counts:
                counts[category] += 1
        return [
            Category(slug=slug, title=title, articles_count=counts[slug])
            for slug, title in CATEGORY_TITLES.items()
        ]
