"""Add hashed admin sessions.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True, comment="SHA-256 of the random session token."),
        sa.Column("username", sa.String(200), nullable=False, comment="Configured administrator that owns the session."),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, comment="When the session was created."),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False, comment="Sliding session expiry in UTC."),
    )
    op.create_index("ix_admin_sessions_expires_at", "admin_sessions", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_admin_sessions_expires_at", table_name="admin_sessions")
    op.drop_table("admin_sessions")
