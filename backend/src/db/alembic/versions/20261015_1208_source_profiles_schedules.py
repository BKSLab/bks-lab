"""Add verified profile identities and individual source calendars.

Revision ID: 0010
Revises: 0009
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("news_sources", sa.Column("profile_id", sa.String(160), nullable=True, comment="Verified code-owned profile identity."))
    op.create_unique_constraint("uq_news_sources_profile_id", "news_sources", ["profile_id"])
    op.add_column("news_sources", sa.Column("description", sa.Text(), nullable=False, server_default="", comment="Editorial source description."))
    op.add_column("news_sources", sa.Column(
        "schedule", postgresql.JSONB(), nullable=False,
        server_default=sa.text("'{\"mode\":\"daily\",\"times\":[\"08:00\",\"14:00\",\"20:00\"]}'::jsonb"),
        comment="Source calendar in Europe/Samara.",
    ))
    op.add_column("news_sources", sa.Column("next_check_at", sa.DateTime(timezone=True), nullable=True, comment="Next automatic collection start."))
    op.create_index("ix_news_sources_next_check_at", "news_sources", ["next_check_at"])


def downgrade() -> None:
    op.drop_index("ix_news_sources_next_check_at", table_name="news_sources")
    op.drop_column("news_sources", "next_check_at")
    op.drop_column("news_sources", "schedule")
    op.drop_column("news_sources", "description")
    op.drop_constraint("uq_news_sources_profile_id", "news_sources", type_="unique")
    op.drop_column("news_sources", "profile_id")
