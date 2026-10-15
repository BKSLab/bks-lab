"""Durable automatic note queue and actual content publication timestamps.

Revision ID: 0011
Revises: 0010
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("content_items", sa.Column("published_at_time", sa.DateTime(timezone=True), nullable=True, comment="Actual first publication instant, independent from the editable date."))
    op.add_column("content_items", sa.Column("source_name", sa.Text(), nullable=True, comment="Automatic note source name snapshot."))
    op.add_column("content_items", sa.Column("source_url", sa.Text(), nullable=True, comment="Automatic note exact source URL snapshot."))
    op.create_index("ix_content_items_note_feed", "content_items", [sa.text("COALESCE(published_at_time, (published_at::timestamp without time zone AT TIME ZONE 'UTC'::text))"), "id"], postgresql_where=sa.text("type = 'note' AND status = 'active'"))
    op.add_column("news_analyses", sa.Column("note_candidate", postgresql.JSONB(), nullable=True, comment="Validated optional Russian note candidate."))
    op.create_table(
        "news_note_settings",
        sa.Column("id", sa.Integer(), primary_key=True, comment="Singleton ID."),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false(), comment="Publication enabled."),
        sa.Column("interval_minutes", sa.Integer(), nullable=False, server_default="10", comment="Minimum publication interval."),
        sa.Column("max_age_hours", sa.Integer(), nullable=False, server_default="72", comment="Maximum source and waiting age."),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True, comment="First activation; immutable on resume."),
        sa.Column("last_published_at", sa.DateTime(timezone=True), nullable=True, comment="Shared durable publication clock."),
        sa.CheckConstraint("id = 1", name="ck_news_note_settings_singleton"),
        sa.CheckConstraint("interval_minutes BETWEEN 10 AND 1440", name="ck_news_note_settings_interval"),
        sa.CheckConstraint("max_age_hours BETWEEN 1 AND 720", name="ck_news_note_settings_age"),
    )
    op.create_table(
        "news_note_queue",
        sa.Column("id", sa.Integer(), primary_key=True, comment="Queue ID."),
        sa.Column("note_slug", sa.String(200), nullable=False, unique=True, comment="Stable note address."),
        sa.Column("content_id", sa.Integer(), sa.ForeignKey("content_items.id", ondelete="SET NULL"), nullable=True, unique=True, comment="Draft or published content; null after editor deletion."),
        sa.Column("source_item_id", sa.Integer(), sa.ForeignKey("news_items.id", ondelete="SET NULL"), nullable=True, comment="Collected material, when retained."),
        sa.Column("analysis_id", sa.Integer(), sa.ForeignKey("news_analyses.id", ondelete="SET NULL"), nullable=True, comment="Original saved analysis, when retained."),
        sa.Column("source_key", sa.String(64), nullable=False, unique=True, comment="Permanent normalized source URL hash."),
        sa.Column("external_key", sa.String(64), nullable=True, unique=True, comment="Permanent profile and external ID hash."),
        sa.Column("content_hash", sa.String(64), nullable=False, comment="Source version used by this note."),
        sa.Column("title", sa.Text(), nullable=False, comment="Last queued title snapshot."),
        sa.Column("text", sa.Text(), nullable=False, comment="Last queued text snapshot."),
        sa.Column("source_name", sa.Text(), nullable=False, comment="Server-owned source name snapshot."),
        sa.Column("source_url", sa.Text(), nullable=False, comment="Server-owned exact article URL snapshot."),
        sa.Column("source_published_at", sa.DateTime(timezone=True), nullable=True, comment="Source publication time snapshot."),
        sa.Column("source_first_seen_at", sa.DateTime(timezone=True), nullable=False, comment="Original ingestion time snapshot."),
        sa.Column("status", sa.String(20), nullable=False, comment="Queue disposition."),
        sa.Column("reason", sa.Text(), nullable=True, comment="Terminal disposition explanation."),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), comment="Queue insertion time."),
        sa.Column("published_at_time", sa.DateTime(timezone=True), nullable=True, comment="Actual note publication time."),
        sa.CheckConstraint("status IN ('queued', 'published', 'excluded', 'expired')", name="ck_news_note_queue_status"),
    )
    op.create_index("ix_news_note_queue_status_created", "news_note_queue", ["status", "created_at", "id"])
    op.create_index("ix_news_note_queue_source_item_id", "news_note_queue", ["source_item_id"])
    op.create_index("ix_news_note_queue_analysis_id", "news_note_queue", ["analysis_id"])


def downgrade() -> None:
    op.drop_table("news_note_queue")
    op.drop_table("news_note_settings")
    op.drop_column("news_analyses", "note_candidate")
    op.drop_index("ix_content_items_note_feed", table_name="content_items")
    op.drop_column("content_items", "source_url")
    op.drop_column("content_items", "source_name")
    op.drop_column("content_items", "published_at_time")
