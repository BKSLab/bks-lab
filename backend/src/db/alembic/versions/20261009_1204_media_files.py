"""Add the media_files table for images uploaded through the admin editor.

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "media_files",
        sa.Column("id", sa.Integer(), nullable=False, comment="Unique identifier of the uploaded file."),
        sa.Column(
            "path",
            sa.String(length=500),
            nullable=False,
            comment="Public path: /uploads/<section>/<file>.webp.",
        ),
        sa.Column(
            "original_name",
            sa.String(length=255),
            nullable=False,
            comment="Original client-side file name.",
        ),
        sa.Column(
            "mime",
            sa.String(length=50),
            nullable=False,
            comment="Stored MIME type (image/webp after conversion).",
        ),
        sa.Column("size_bytes", sa.Integer(), nullable=False, comment="Stored file size in bytes."),
        sa.Column("width", sa.Integer(), nullable=True, comment="Pixel width after conversion."),
        sa.Column("height", sa.Integer(), nullable=True, comment="Pixel height after conversion."),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            comment="When the file was uploaded.",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("path"),
    )


def downgrade() -> None:
    op.drop_table("media_files")
