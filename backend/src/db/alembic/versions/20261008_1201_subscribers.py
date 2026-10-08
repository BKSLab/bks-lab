"""Add the subscriber registry.

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "subscribers",
        sa.Column("email", sa.String(254), primary_key=True, comment="Normalized subscriber email address."),
        sa.Column("subscribed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, comment="UTC time of the first subscription."),
    )
    op.create_index("ix_subscribers_subscribed_at", "subscribers", ["subscribed_at"])


def downgrade() -> None:
    op.drop_index("ix_subscribers_subscribed_at", table_name="subscribers")
    op.drop_table("subscribers")
