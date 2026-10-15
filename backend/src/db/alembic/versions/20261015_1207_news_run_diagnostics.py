"""Add readable news addresses and persistent collection observations.

Revision ID: 0009
Revises: 0008
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("news_sources", sa.Column("slug", sa.String(160), nullable=False, comment="Stable readable address."))
    op.create_unique_constraint("uq_news_sources_slug", "news_sources", ["slug"])
    op.add_column("news_jobs", sa.Column("slug", sa.String(240), nullable=False, comment="Stable readable queue address."))
    op.create_unique_constraint("uq_news_jobs_slug", "news_jobs", ["slug"])
    columns = (
        sa.Column("source_name", sa.String(200), nullable=False, comment="Source name at start."),
        sa.Column("source_slug", sa.String(160), nullable=False, comment="Source address at start."),
        sa.Column("source_url", sa.Text(), nullable=False, comment="Source URL at start."),
        sa.Column("source_kind", sa.String(10), nullable=False, comment="Adapter at start."),
        sa.Column("parameters", postgresql.JSONB(), nullable=False, comment="Safe collection parameters."),
        sa.Column("not_modified", sa.Boolean(), nullable=False, comment="Conditional request returned no changes."),
        sa.Column("http_status", sa.Integer(), nullable=True, comment="Final source HTTP status."),
        sa.Column("limit_reached", sa.Boolean(), nullable=False, comment="Collection candidate limit reached."),
        sa.Column("diagnostics_truncated", sa.Boolean(), nullable=False, comment="Detailed observation limit reached."),
        sa.Column("skipped_count", sa.Integer(), nullable=False, comment="Skipped candidates."),
        sa.Column("warning_count", sa.Integer(), nullable=False, comment="Candidates with collection warnings."),
    )
    for column in columns:
        op.add_column("news_source_runs", column)
    op.create_index("ix_news_source_runs_source_slug", "news_source_runs", ["source_slug"])
    op.create_table(
        "news_run_items",
        sa.Column("id", sa.Integer(), primary_key=True, comment="Observation ID."),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("news_source_runs.id", ondelete="CASCADE"), nullable=False, comment="Owning source run."),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("news_items.id", ondelete="SET NULL"), nullable=True, comment="Material if retained."),
        sa.Column("title", sa.String(1000), nullable=False, comment="Observed title."),
        sa.Column("url", sa.Text(), nullable=True, comment="Observed URL."),
        sa.Column("outcome", sa.String(12), nullable=False, comment="Ingestion outcome."),
        sa.Column("reason", sa.String(500), nullable=True, comment="Safe outcome explanation."),
        sa.Column("warning", sa.String(500), nullable=True, comment="Safe collection warning."),
        sa.Column("stage", sa.String(32), nullable=True, comment="Collection stage."),
        sa.Column("preserved_previous", sa.Boolean(), nullable=False, comment="Previous sufficient text preserved."),
        sa.Column("content_hash", sa.String(64), nullable=True, comment="Observed retained version."),
        sa.CheckConstraint("outcome IN ('new', 'updated', 'unchanged', 'skipped')", name="ck_news_run_items_outcome"),
    )
    op.create_index("ix_news_run_items_item_id", "news_run_items", ["item_id"])
    op.create_index("ix_news_run_items_run_outcome", "news_run_items", ["run_id", "outcome"])
    op.create_index("ix_news_run_items_run_warning", "news_run_items", ["run_id"], postgresql_where=sa.text("warning IS NOT NULL"))


def downgrade() -> None:
    op.drop_table("news_run_items")
    op.drop_index("ix_news_source_runs_source_slug", table_name="news_source_runs")
    for column in (
        "warning_count", "skipped_count", "diagnostics_truncated", "limit_reached",
        "http_status", "not_modified", "parameters", "source_kind", "source_url",
        "source_slug", "source_name",
    ):
        op.drop_column("news_source_runs", column)
    op.drop_constraint("uq_news_jobs_slug", "news_jobs", type_="unique")
    op.drop_column("news_jobs", "slug")
    op.drop_constraint("uq_news_sources_slug", "news_sources", type_="unique")
    op.drop_column("news_sources", "slug")
