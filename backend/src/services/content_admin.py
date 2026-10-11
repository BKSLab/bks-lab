"""Admin content mutations: CRUD, status transitions and revision restore.

Every save validates the effective state against the type-specific schema,
re-derives stored fields (rendered HTML, plain text, word count, reading
time, note excerpt) and writes the row plus a revision snapshot in ONE
transaction: the repositories only flush here, the service commits.
"""

import logging
from typing import Any

from pydantic import BaseModel, ValidationError

from src.clients.revalidation import RevalidationClient
from src.db.models import ContentItem
from src.exceptions.admin import AdminContentNotFoundError, AdMarkerError, ContentValidationError
from src.repositories.content_items import ContentItemRepository
from src.repositories.content_revisions import ContentRevisionRepository
from src.schemas.admin import (
    ArticleCreate,
    ContentCreate,
    ContentItemFull,
    ContentPatch,
    ContentRevisionDetail,
    ContentRevisionRow,
    NoteCreate,
    ProjectCreate,
)
from src.services.content_fields import (
    ContentFields,
    build_item_values,
    build_snapshot,
    resolve_status,
    snapshot_to_values,
)
from src.utils import markdown as md

logger = logging.getLogger(__name__)

CREATE_SCHEMAS: dict[str, type[BaseModel]] = {
    "article": ArticleCreate,
    "note": NoteCreate,
    "project": ProjectCreate,
}

# Editable columns mirrored between a stored row and the merge base of a patch.
_MERGE_FIELDS = (
    "title", "excerpt", "category", "published_at", "cover_image", "tags",
    "seo_title", "seo_description", "og_image", "related_slug",
    "featured", "sort_order", "content_markdown",
)


def _fields_from_payload(data: BaseModel) -> ContentFields:
    """Normalize a validated create payload into editable fields."""
    return ContentFields(
        title=data.title,
        status=resolve_status(
            draft=data.draft, lifecycle=getattr(data, "status", None)
        ),
        content_markdown=data.content_markdown,
        category=getattr(data, "category", None),
        tags=list(getattr(data, "tags", []) or []),
        published_at=getattr(data, "published_at", None),
        excerpt=getattr(data, "excerpt", None),
        cover_image=getattr(data, "cover_image", None),
        seo_title=getattr(data, "seo_title", None),
        seo_description=getattr(data, "seo_description", None),
        og_image=getattr(data, "og_image", None),
        related_slug=getattr(data, "related_slug", None),
        featured=getattr(data, "featured", False),
        sort_order=getattr(data, "sort_order", None),
        reading_time_override=getattr(data, "reading_time", None),
    )


class ContentAdminService:
    """Use-cases of the content editor (write path of /api/admin/content)."""

    def __init__(
        self,
        *,
        items: ContentItemRepository,
        revisions: ContentRevisionRepository,
        revalidator: RevalidationClient,
        words_per_minute: int,
    ) -> None:
        self.items = items
        self.revisions = revisions
        self.revalidator = revalidator
        self.words_per_minute = words_per_minute

    # Public use-cases

    async def create_item(self, data: ContentCreate) -> ContentItemFull:
        """Create a material (draft unless the payload says otherwise).

        Raises:
            AdMarkerError: On a misplaced inline ad marker.
            ContentItemConflictError: On a duplicate (type, slug) — 409.
        """
        self._check_ad_markers(data.type, data.content_markdown)
        fields = _fields_from_payload(data)
        values = build_item_values(data.type, data.slug, fields, self.words_per_minute)
        item = await self.items.add(values)
        await self.revisions.add(
            item_id=item.id, snapshot=build_snapshot(values), word_count=values["word_count"]
        )
        await self.items.commit()
        await self.revalidator.revalidate_content()
        logger.info("Created %s %s (id=%s)", item.type, item.slug, item.id)
        return ContentItemFull.model_validate(item)

    async def update_item(self, item_id: int, data: ContentPatch) -> ContentItemFull:
        """Apply a partial edit; the merged state is validated per type.

        Raises:
            AdminContentNotFoundError: When the material does not exist.
            ContentValidationError: When the merged state violates type rules.
        """
        item = await self._get_or_raise(item_id)
        validated = self._validate_merged(item, data.model_dump(exclude_unset=True))
        self._check_ad_markers(item.type, validated.content_markdown)
        fields = _fields_from_payload(validated)
        values = build_item_values(item.type, item.slug, fields, self.words_per_minute)
        await self.items.apply(item, values)
        await self.revisions.add(
            item_id=item.id, snapshot=build_snapshot(values), word_count=values["word_count"]
        )
        await self.items.commit()
        await self.revalidator.revalidate_content()
        logger.info("Updated %s %s (id=%s)", item.type, item.slug, item.id)
        return ContentItemFull.model_validate(item)

    async def delete_item(self, item_id: int) -> None:
        """Delete a material; revisions are removed by the FK cascade.

        Raises:
            AdminContentNotFoundError: When the material does not exist.
        """
        item = await self._get_or_raise(item_id)
        await self.items.remove(item)
        await self.items.commit()
        await self.revalidator.revalidate_content()
        logger.info("Deleted %s %s (id=%s)", item.type, item.slug, item.id)

    async def set_status(self, item_id: int, status: str) -> ContentItemFull:
        """Transition the status; archived is valid for projects only.

        Raises:
            AdminContentNotFoundError: When the material does not exist.
            ContentValidationError: When a non-project is archived.
        """
        item = await self._get_or_raise(item_id)
        if status == "archived" and item.type != "project":
            raise ContentValidationError
        await self.items.apply(item, {"status": status})
        snapshot = self._snapshot_of(item)
        snapshot["status"] = status
        await self.revisions.add(
            item_id=item.id, snapshot=snapshot, word_count=item.word_count
        )
        await self.items.commit()
        await self.revalidator.revalidate_content()
        logger.info("Status of %s %s (id=%s) set to %s", item.type, item.slug, item.id, status)
        return ContentItemFull.model_validate(item)

    async def list_revisions(self, item_id: int) -> list[ContentRevisionRow]:
        """List version metadata of a material, newest first.

        Raises:
            AdminContentNotFoundError: When the material does not exist.
        """
        await self._get_or_raise(item_id)
        rows = await self.revisions.list_for_item(item_id)
        return [ContentRevisionRow.model_validate(row) for row in rows]

    async def get_revision(self, item_id: int, revision_no: int) -> ContentRevisionDetail:
        """Read one version snapshot.

        Raises:
            AdminContentNotFoundError: When the material or version is missing.
        """
        await self._get_or_raise(item_id)
        revision = await self.revisions.get(item_id, revision_no)
        if revision is None:
            raise AdminContentNotFoundError
        return ContentRevisionDetail.model_validate(revision)

    def render_preview(self, content_markdown: str) -> str:
        """Render Markdown to HTML for the live editor preview.

        Uses the same pipeline that derives stored content_html on every
        save; nothing is written to the database and no revalidation fires.
        """
        return md.render_markdown(content_markdown)

    async def restore_revision(self, item_id: int, revision_no: int) -> ContentItemFull:
        """Copy a version snapshot back into the row and record a new revision.

        History is never rewritten: the restore itself is a new revision.

        Raises:
            AdminContentNotFoundError: When the material or version is missing.
        """
        item = await self._get_or_raise(item_id)
        revision = await self.revisions.get(item_id, revision_no)
        if revision is None:
            raise AdminContentNotFoundError
        values = snapshot_to_values(revision.snapshot)
        await self.items.apply(item, values)
        await self.revisions.add(
            item_id=item.id, snapshot=dict(revision.snapshot), word_count=revision.word_count
        )
        await self.items.commit()
        await self.revalidator.revalidate_content()
        logger.info("Restored %s %s (id=%s) to revision %s", item.type, item.slug, item.id, revision_no)
        return ContentItemFull.model_validate(item)

    # Internal helpers

    @staticmethod
    def _check_ad_markers(content_type: str, content_markdown: str) -> None:
        """Enforce the inline ad placement rules (docs/content_editor.md §7)."""
        if md.ad_marker_error(content_type, content_markdown) is not None:
            raise AdMarkerError

    async def _get_or_raise(self, item_id: int) -> ContentItem:
        item = await self.items.get_by_id(item_id)
        if item is None:
            raise AdminContentNotFoundError
        return item

    @staticmethod
    def _snapshot_of(item: ContentItem) -> dict[str, Any]:
        """Snapshot the current row state (used by status transitions)."""
        return build_snapshot(
            {key: getattr(item, key) for key in (*_MERGE_FIELDS, "status", "reading_time", "word_count", "content_text", "content_html")}
        )

    @staticmethod
    def _validate_merged(item: ContentItem, updates: dict[str, Any]) -> BaseModel:
        """Merge a patch onto the stored row and validate per content type."""
        merged: dict[str, Any] = {key: getattr(item, key) for key in _MERGE_FIELDS}
        merged["draft"] = item.status == "draft"
        merged["status"] = item.status if item.status != "draft" else "active"
        # A stored reading_time is the computed value, not necessarily an
        # explicit override; an omitted patch field means "recompute".
        merged["reading_time"] = None
        merged.update(updates)
        schema = CREATE_SCHEMAS[item.type]
        allowed = set(schema.model_fields)
        payload = {key: value for key, value in merged.items() if key in allowed}
        try:
            return schema.model_validate({**payload, "type": item.type, "slug": item.slug})
        except ValidationError as error:
            raise ContentValidationError from error
