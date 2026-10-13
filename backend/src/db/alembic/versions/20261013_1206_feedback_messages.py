"""Store feedback messages for the admin inbox.

Revision ID: 0008
Revises: 0007
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "feedback_messages",
        sa.Column("id", sa.Integer(), primary_key=True, comment="Message ID."),
        sa.Column("name", sa.String(100), nullable=False, comment="Visitor name."),
        sa.Column("email", sa.String(254), nullable=False, comment="Visitor contact address for a manual reply."),
        sa.Column("message", sa.Text(), nullable=False, comment="Plain-text visitor message."),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, comment="UTC time the message was received."),
    )
    op.create_index("ix_feedback_messages_created_at", "feedback_messages", ["created_at", "id"])


def downgrade() -> None:
    op.drop_index("ix_feedback_messages_created_at", table_name="feedback_messages")
    op.drop_table("feedback_messages")
