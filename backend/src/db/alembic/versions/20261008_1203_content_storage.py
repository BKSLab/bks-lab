"""Turn content_items into the primary content storage; add content_revisions.

DDL only, no backfill: existing projection rows keep NULL in
content_markdown/content_html until the one-time import fills them.
Downgrade re-adds content_hash as nullable so it stays runnable on a
populated table.

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import Text
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "content_items",
        sa.Column(
            "excerpt",
            sa.Text(),
            nullable=True,
            comment="Annotation; notes store the first paragraph computed on write.",
        ),
    )
    op.add_column(
        "content_items",
        sa.Column(
            "cover_image",
            sa.String(length=500),
            nullable=True,
            comment="Cover image path (/images/... or /uploads/...).",
        ),
    )
    op.add_column(
        "content_items",
        sa.Column(
            "seo_title",
            sa.Text(),
            nullable=True,
            comment="SEO title override; defaults to the title.",
        ),
    )
    op.add_column(
        "content_items",
        sa.Column(
            "seo_description",
            sa.Text(),
            nullable=True,
            comment="SEO description override; defaults to the excerpt.",
        ),
    )
    op.add_column(
        "content_items",
        sa.Column(
            "og_image",
            sa.String(length=500),
            nullable=True,
            comment="Open Graph image override.",
        ),
    )
    op.add_column(
        "content_items",
        sa.Column(
            "related_slug",
            sa.String(length=200),
            nullable=True,
            comment="Notes only: slug of the related article.",
        ),
    )
    op.add_column(
        "content_items",
        sa.Column(
            "featured",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
            comment="Projects: shown on the home page when true.",
        ),
    )
    op.add_column(
        "content_items",
        sa.Column(
            "sort_order",
            sa.Integer(),
            nullable=True,
            comment="Projects: explicit ordering on the home page.",
        ),
    )
    op.add_column(
        "content_items",
        sa.Column(
            "content_markdown",
            sa.Text(),
            nullable=True,
            comment="Source Markdown body.",
        ),
    )
    op.add_column(
        "content_items",
        sa.Column(
            "content_html",
            sa.Text(),
            nullable=True,
            comment="Rendered HTML cache; produced on write, never on read.",
        ),
    )
    op.add_column(
        "content_items",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            comment="When the material was created.",
        ),
    )
    op.add_column(
        "content_items",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            comment="When the material was last saved.",
        ),
    )
    op.drop_column("content_items", "content_hash")
    op.drop_column("content_items", "synced_at")

    # Keep DB comments in sync with the model for columns whose meaning
    # changed when files stopped being the source of truth.
    op.alter_column(
        "content_items", "slug",
        existing_type=sa.String(length=200), existing_nullable=False,
        comment="URL slug; unique within the type.",
    )
    op.alter_column(
        "content_items", "title",
        existing_type=sa.Text(), existing_nullable=False,
        comment="Material title.",
    )
    op.alter_column(
        "content_items", "status",
        existing_type=sa.String(length=20), existing_nullable=False,
        comment="Publication status: active | draft | archived (archived is projects-only).",
    )

    op.create_table(
        "content_revisions",
        sa.Column("id", sa.Integer(), nullable=False, comment="Unique identifier of the revision."),
        sa.Column(
            "item_id",
            sa.Integer(),
            nullable=False,
            comment="FK to content_items; revisions are deleted with the material.",
        ),
        sa.Column(
            "revision_no",
            sa.Integer(),
            nullable=False,
            comment="Sequential version number within the material.",
        ),
        sa.Column(
            "snapshot",
            postgresql.JSONB(astext_type=Text()),
            nullable=False,
            comment="Snapshot of all editable fields, including the Markdown body.",
        ),
        sa.Column(
            "word_count",
            sa.Integer(),
            nullable=False,
            comment="Word count at save time; shown in the version list.",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            comment="When this version was saved.",
        ),
        sa.ForeignKeyConstraint(["item_id"], ["content_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_content_revisions_item_revision",
        "content_revisions",
        ["item_id", "revision_no"],
        unique=True,
    )
    op.create_index("ix_content_revisions_item_id", "content_revisions", ["item_id"])


def downgrade() -> None:
    op.drop_index("ix_content_revisions_item_id", table_name="content_revisions")
    op.drop_index("uq_content_revisions_item_revision", table_name="content_revisions")
    op.drop_table("content_revisions")

    op.add_column(
        "content_items",
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            comment="When the row was last written by the content sync.",
        ),
    )
    op.add_column(
        "content_items",
        sa.Column(
            "content_hash",
            sa.String(length=64),
            nullable=True,
            comment="SHA-256 of the raw file; unchanged files are skipped on sync.",
        ),
    )
    for column in (
        "updated_at", "created_at", "content_html", "content_markdown",
        "sort_order", "featured", "related_slug", "og_image",
        "seo_description", "seo_title", "cover_image", "excerpt",
    ):
        op.drop_column("content_items", column)
