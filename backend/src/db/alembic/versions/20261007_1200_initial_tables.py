"""Initial tables: page_views and content_items.

Revision ID: 0001
Revises:
Create Date: 2026-10-07

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "page_views",
        sa.Column("id", sa.Integer(), nullable=False, comment="Unique identifier of the page view row."),
        sa.Column(
            "viewed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            comment="When the view happened (server time, UTC).",
        ),
        sa.Column(
            "path",
            sa.String(length=500),
            nullable=False,
            comment="Normalized site path without query string and anchor.",
        ),
        sa.Column(
            "note_slug",
            sa.String(length=200),
            nullable=True,
            comment="Slug extracted from a #note-<slug> anchor on the /notes feed.",
        ),
        sa.Column(
            "referrer_domain",
            sa.String(length=255),
            nullable=True,
            comment="Referrer domain only (no path/query); null when absent or invalid.",
        ),
        sa.Column(
            "visitor_hash",
            sa.String(length=64),
            nullable=False,
            comment="sha256(daily_salt + ip + user_agent); daily salt = HMAC(stats_secret, UTC date).",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_page_views_viewed_at", "page_views", ["viewed_at"])
    op.create_index("ix_page_views_path_viewed_at", "page_views", ["path", "viewed_at"])

    op.create_table(
        "content_items",
        sa.Column("id", sa.Integer(), nullable=False, comment="Unique identifier of the content item."),
        sa.Column(
            "type",
            sa.String(length=20),
            nullable=False,
            comment="Content type: article | note | project.",
        ),
        sa.Column(
            "slug",
            sa.String(length=200),
            nullable=False,
            comment="Slug from the file name; unique within the type.",
        ),
        sa.Column("title", sa.Text(), nullable=False, comment="Title from frontmatter."),
        sa.Column(
            "category",
            sa.String(length=50),
            nullable=True,
            comment="Blog category slug; only articles have one.",
        ),
        sa.Column(
            "tags",
            postgresql.JSONB(),
            nullable=False,
            comment="Free-form tags as a JSON array.",
        ),
        sa.Column(
            "published_at",
            sa.Date(),
            nullable=True,
            comment="Publication date; null for projects (not dated).",
        ),
        sa.Column(
            "reading_time",
            sa.Integer(),
            nullable=True,
            comment="Reading time in minutes; articles and notes only.",
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            comment="Projection status: active | draft | archived (archived is projects-only).",
        ),
        sa.Column(
            "word_count",
            sa.Integer(),
            nullable=False,
            comment="Word count of the plain-text body.",
        ),
        sa.Column(
            "content_text",
            sa.Text(),
            nullable=False,
            comment="Plain-text body extracted from Markdown (for analysis).",
        ),
        sa.Column(
            "content_hash",
            sa.String(length=64),
            nullable=False,
            comment="SHA-256 of the raw file; unchanged files are skipped on sync.",
        ),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            comment="When the row was last written by the content sync.",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("type", "slug", name="uq_content_items_type_slug"),
    )


def downgrade() -> None:
    op.drop_table("content_items")
    op.drop_index("ix_page_views_path_viewed_at", table_name="page_views")
    op.drop_index("ix_page_views_viewed_at", table_name="page_views")
    op.drop_table("page_views")
