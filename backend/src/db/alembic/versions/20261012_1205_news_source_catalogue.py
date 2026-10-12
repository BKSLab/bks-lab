"""Store source catalogue suggestions separately from connected sources.

Revision ID: 0007
Revises: 0006
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "news_source_catalogue",
        sa.Column("id", sa.String(100), nullable=False, comment="Stable research entry ID."),
        sa.Column(
            "position", sa.Integer(), nullable=False,
            comment="Display order in the research catalogue.",
        ),
        sa.Column(
            "data", postgresql.JSONB(), nullable=False,
            comment="Suggestion metadata, URLs and connection notes; not a verified source.",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_news_source_catalogue_position", "news_source_catalogue", ["position"])


def downgrade() -> None:
    op.drop_index("ix_news_source_catalogue_position", table_name="news_source_catalogue")
    op.drop_table("news_source_catalogue")
