"""Add News Analyzer storage and durable background jobs.

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import Text
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "news_categories",
        sa.Column("id", sa.Integer(), nullable=False, comment="Category ID."),
        sa.Column(
            "name", sa.String(length=120), nullable=False, comment="Category name."
        ),
        sa.Column(
            "description", sa.Text(), nullable=False, comment="Editorial description."
        ),
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            comment="Available for new analysis.",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(
        op.f("ix_news_categories_active"), "news_categories", ["active"], unique=False
    )
    op.create_table(
        "news_settings",
        sa.Column("id", sa.Integer(), nullable=False, comment="Singleton key."),
        sa.Column(
            "value",
            postgresql.JSONB(astext_type=Text()),
            nullable=False,
            comment="Validated editorial configuration.",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Last settings change.",
        ),
        sa.CheckConstraint("id = 1", name="ck_news_settings_singleton"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "news_sources",
        sa.Column("id", sa.Integer(), nullable=False, comment="Source ID."),
        sa.Column(
            "name", sa.String(length=200), nullable=False, comment="Display name."
        ),
        sa.Column(
            "url", sa.Text(), nullable=False, comment="Checked feed or listing URL."
        ),
        sa.Column(
            "kind", sa.String(length=10), nullable=False, comment="RSS or HTML adapter."
        ),
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=Text()),
            nullable=False,
            comment="Adapter selectors.",
        ),
        sa.Column(
            "active", sa.Boolean(), nullable=False, comment="Collection enabled."
        ),
        sa.Column(
            "priority", sa.Integer(), nullable=False, comment="Collection priority."
        ),
        sa.Column(
            "trust_score",
            sa.Integer(),
            nullable=False,
            comment="Editorial source trust.",
        ),
        sa.Column(
            "vendor_affiliated",
            sa.Boolean(),
            nullable=False,
            comment="Commercial affiliation flag.",
        ),
        sa.Column(
            "interval_hours",
            sa.Integer(),
            nullable=False,
            comment="Minimum collection interval.",
        ),
        sa.Column(
            "cursor",
            postgresql.JSONB(astext_type=Text()),
            nullable=False,
            comment="Last committed adapter cursor.",
        ),
        sa.Column("etag", sa.Text(), nullable=True, comment="Last committed ETag."),
        sa.Column(
            "last_modified",
            sa.Text(),
            nullable=True,
            comment="Last committed Last-Modified.",
        ),
        sa.Column(
            "last_success_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Last committed successful fetch.",
        ),
        sa.Column(
            "last_error", sa.Text(), nullable=True, comment="Safe error summary."
        ),
        sa.Column(
            "last_new_count",
            sa.Integer(),
            nullable=False,
            comment="New items in latest fetch.",
        ),
        sa.Column(
            "health", sa.String(length=20), nullable=False, comment="Collection health."
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Creation time.",
        ),
        sa.CheckConstraint("kind IN ('rss', 'html')", name="ck_news_sources_kind"),
        sa.CheckConstraint("interval_hours >= 1", name="ck_news_sources_interval"),
        sa.CheckConstraint(
            "priority BETWEEN 0 AND 100", name="ck_news_sources_priority"
        ),
        sa.CheckConstraint(
            "trust_score BETWEEN 0 AND 100", name="ck_news_sources_trust"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_news_sources_active"), "news_sources", ["active"], unique=False
    )
    op.create_index(
        op.f("ix_news_sources_last_success_at"),
        "news_sources",
        ["last_success_at"],
        unique=False,
    )
    op.create_table(
        "news_topics",
        sa.Column("id", sa.Integer(), nullable=False, comment="Topic ID."),
        sa.Column("name", sa.String(length=120), nullable=False, comment="Topic name."),
        sa.Column(
            "description", sa.Text(), nullable=False, comment="Editorial description."
        ),
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            comment="Available for new analysis.",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(
        op.f("ix_news_topics_active"), "news_topics", ["active"], unique=False
    )
    op.create_table(
        "news_items",
        sa.Column("id", sa.Integer(), nullable=False, comment="Item ID."),
        sa.Column("source_id", sa.Integer(), nullable=False, comment="Owning source."),
        sa.Column(
            "external_id",
            sa.String(length=1000),
            nullable=True,
            comment="RSS GUID or provider identifier.",
        ),
        sa.Column("url", sa.Text(), nullable=False, comment="Original article URL."),
        sa.Column(
            "canonical_url", sa.Text(), nullable=True, comment="Canonical article URL."
        ),
        sa.Column(
            "normalized_url",
            sa.String(length=2000),
            nullable=False,
            comment="Normalized deduplication URL.",
        ),
        sa.Column("title", sa.Text(), nullable=False, comment="Plain text title."),
        sa.Column(
            "excerpt", sa.Text(), nullable=False, comment="Bounded plain text excerpt."
        ),
        sa.Column(
            "content", sa.Text(), nullable=False, comment="Retained cleaned text."
        ),
        sa.Column(
            "content_hash",
            sa.String(length=64),
            nullable=False,
            comment="Hash of significant source content.",
        ),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=Text()),
            nullable=False,
            comment="Adapter metadata.",
        ),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Source publication time.",
        ),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="First ingestion time.",
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Latest observation time.",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Source update time.",
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            comment="Current analysis state.",
        ),
        sa.Column(
            "duplicate_of_id",
            sa.Integer(),
            nullable=True,
            comment="Earlier cross-source copy.",
        ),
        sa.Column(
            "latest_analysis_id",
            sa.Integer(),
            nullable=True,
            comment="Analysis for the current content.",
        ),
        sa.Column(
            "latest_decision_id",
            sa.Integer(),
            nullable=True,
            comment="Latest editorial decision.",
        ),
        sa.CheckConstraint(
            "status IN ('pending_analysis', 'analyzed')", name="ck_news_items_status"
        ),
        sa.ForeignKeyConstraint(
            ["duplicate_of_id"], ["news_items.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["source_id"], ["news_sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_id", "external_id", name="uq_news_items_source_external"
        ),
        sa.UniqueConstraint(
            "source_id", "normalized_url", name="uq_news_items_source_url"
        ),
    )
    op.create_index(
        op.f("ix_news_items_duplicate_of_id"),
        "news_items",
        ["duplicate_of_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_news_items_first_seen_at"),
        "news_items",
        ["first_seen_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_news_items_latest_analysis_id"),
        "news_items",
        ["latest_analysis_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_news_items_normalized_url"),
        "news_items",
        ["normalized_url"],
        unique=False,
    )
    op.create_index(
        op.f("ix_news_items_published_at"), "news_items", ["published_at"], unique=False
    )
    op.create_index(
        op.f("ix_news_items_source_id"), "news_items", ["source_id"], unique=False
    )
    op.create_index(
        "ix_news_items_status_seen",
        "news_items",
        ["status", "first_seen_at"],
        unique=False,
    )
    op.create_table(
        "news_source_categories",
        sa.Column("source_id", sa.Integer(), nullable=False, comment="Source ID."),
        sa.Column("category_id", sa.Integer(), nullable=False, comment="Category ID."),
        sa.ForeignKeyConstraint(
            ["category_id"], ["news_categories.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["source_id"], ["news_sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("source_id", "category_id"),
    )
    op.create_index(
        op.f("ix_news_source_categories_category_id"),
        "news_source_categories",
        ["category_id"],
        unique=False,
    )
    op.create_table(
        "news_source_topics",
        sa.Column("source_id", sa.Integer(), nullable=False, comment="Source ID."),
        sa.Column("topic_id", sa.Integer(), nullable=False, comment="Topic ID."),
        sa.ForeignKeyConstraint(["source_id"], ["news_sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["topic_id"], ["news_topics.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("source_id", "topic_id"),
    )
    op.create_index(
        op.f("ix_news_source_topics_topic_id"),
        "news_source_topics",
        ["topic_id"],
        unique=False,
    )
    op.create_table(
        "news_analyses",
        sa.Column("id", sa.Integer(), nullable=False, comment="Analysis ID."),
        sa.Column("item_id", sa.Integer(), nullable=False, comment="Collected item."),
        sa.Column(
            "content_hash",
            sa.String(length=64),
            nullable=False,
            comment="Analyzed content version.",
        ),
        sa.Column(
            "model",
            sa.String(length=200),
            nullable=False,
            comment="Provider model name.",
        ),
        sa.Column(
            "prompt_version",
            sa.String(length=100),
            nullable=False,
            comment="Editorial prompt version.",
        ),
        sa.Column(
            "is_relevant",
            sa.Boolean(),
            nullable=False,
            comment="Model relevance classification.",
        ),
        sa.Column(
            "category_id",
            sa.Integer(),
            nullable=True,
            comment="Existing editorial category.",
        ),
        sa.Column(
            "suggested_topics",
            postgresql.JSONB(astext_type=Text()),
            nullable=False,
            comment="Suggestions outside the taxonomy.",
        ),
        sa.Column(
            "scores",
            postgresql.JSONB(astext_type=Text()),
            nullable=False,
            comment="Validated criterion scores.",
        ),
        sa.Column("summary_ru", sa.Text(), nullable=False, comment="Russian summary."),
        sa.Column(
            "editorial_comment_ru",
            sa.Text(),
            nullable=False,
            comment="Editorial explanation.",
        ),
        sa.Column(
            "recommended_formats",
            postgresql.JSONB(astext_type=Text()),
            nullable=False,
            comment="Recommended editorial formats.",
        ),
        sa.Column(
            "confidence", sa.Float(), nullable=False, comment="Model confidence."
        ),
        sa.Column(
            "needs_verification",
            sa.Boolean(),
            nullable=False,
            comment="Requires fact verification.",
        ),
        sa.Column(
            "news_score",
            sa.Float(),
            nullable=False,
            comment="Python weighted news score.",
        ),
        sa.Column(
            "article_score",
            sa.Float(),
            nullable=False,
            comment="Python weighted article score.",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Analysis completion time.",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"], ["news_categories.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["item_id"], ["news_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "item_id",
            "content_hash",
            "model",
            "prompt_version",
            name="uq_news_analyses_identity",
        ),
    )
    op.create_index(
        op.f("ix_news_analyses_article_score"),
        "news_analyses",
        ["article_score"],
        unique=False,
    )
    op.create_index(
        op.f("ix_news_analyses_category_id"),
        "news_analyses",
        ["category_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_news_analyses_created_at"),
        "news_analyses",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_news_analyses_formats",
        "news_analyses",
        ["recommended_formats"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_index(
        op.f("ix_news_analyses_item_id"), "news_analyses", ["item_id"], unique=False
    )
    op.create_index(
        op.f("ix_news_analyses_news_score"),
        "news_analyses",
        ["news_score"],
        unique=False,
    )
    op.create_table(
        "news_editorial_decisions",
        sa.Column("id", sa.Integer(), nullable=False, comment="Decision ID."),
        sa.Column("item_id", sa.Integer(), nullable=False, comment="Collected item."),
        sa.Column(
            "decision",
            sa.String(length=20),
            nullable=False,
            comment="Editorial disposition.",
        ),
        sa.Column(
            "format",
            sa.String(length=30),
            nullable=False,
            comment="Editorial destination.",
        ),
        sa.Column("comment", sa.Text(), nullable=False, comment="Editor comment."),
        sa.Column(
            "editor",
            sa.String(length=200),
            nullable=False,
            comment="Authenticated editor identity.",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Decision time.",
        ),
        sa.CheckConstraint(
            "decision IN ('in_work', 'deferred', 'rejected')",
            name="ck_news_decisions_decision",
        ),
        sa.CheckConstraint(
            "format IN ('longread_candidate', 'short_news_candidate')",
            name="ck_news_decisions_format",
        ),
        sa.ForeignKeyConstraint(["item_id"], ["news_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_news_editorial_decisions_created_at"),
        "news_editorial_decisions",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_news_editorial_decisions_decision"),
        "news_editorial_decisions",
        ["decision"],
        unique=False,
    )
    op.create_index(
        op.f("ix_news_editorial_decisions_item_id"),
        "news_editorial_decisions",
        ["item_id"],
        unique=False,
    )
    op.create_table(
        "news_jobs",
        sa.Column("id", sa.Integer(), nullable=False, comment="Job ID."),
        sa.Column(
            "kind", sa.String(length=12), nullable=False, comment="Pipeline stage."
        ),
        sa.Column(
            "status", sa.String(length=12), nullable=False, comment="Queue state."
        ),
        sa.Column(
            "source_id", sa.Integer(), nullable=True, comment="Optional source scope."
        ),
        sa.Column(
            "item_id", sa.Integer(), nullable=True, comment="Optional item scope."
        ),
        sa.Column(
            "dedupe_key",
            sa.String(length=500),
            nullable=True,
            comment="Stable scheduler or analysis identity.",
        ),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=Text()),
            nullable=False,
            comment="Validated work parameters.",
        ),
        sa.Column(
            "result",
            postgresql.JSONB(astext_type=Text()),
            nullable=True,
            comment="Safe stage result.",
        ),
        sa.Column(
            "progress",
            postgresql.JSONB(astext_type=Text()),
            nullable=False,
            comment="Stage counters.",
        ),
        sa.Column("error", sa.Text(), nullable=True, comment="Safe failure summary."),
        sa.Column(
            "attempts", sa.Integer(), nullable=False, comment="Acquisition count."
        ),
        sa.Column(
            "owner_token",
            sa.String(length=100),
            nullable=True,
            comment="Lease ownership token.",
        ),
        sa.Column(
            "lease_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Lease expiry.",
        ),
        sa.Column(
            "heartbeat_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Last valid heartbeat.",
        ),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Earliest retry time.",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Enqueue time.",
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Latest acquisition time.",
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Terminal state time.",
        ),
        sa.CheckConstraint(
            "kind IN ('collect', 'discover', 'analyze')", name="ck_news_jobs_kind"
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_news_jobs_status",
        ),
        sa.ForeignKeyConstraint(["item_id"], ["news_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["news_sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedupe_key"),
    )
    op.create_index(
        op.f("ix_news_jobs_created_at"), "news_jobs", ["created_at"], unique=False
    )
    op.create_index(
        op.f("ix_news_jobs_item_id"), "news_jobs", ["item_id"], unique=False
    )
    op.create_index(
        op.f("ix_news_jobs_lease_expires_at"),
        "news_jobs",
        ["lease_expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_news_jobs_queue",
        "news_jobs",
        ["status", "kind", "available_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_news_jobs_source_id"), "news_jobs", ["source_id"], unique=False
    )
    op.create_table(
        "news_analysis_topics",
        sa.Column("analysis_id", sa.Integer(), nullable=False, comment="Analysis ID."),
        sa.Column("topic_id", sa.Integer(), nullable=False, comment="Topic ID."),
        sa.ForeignKeyConstraint(
            ["analysis_id"], ["news_analyses.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["topic_id"], ["news_topics.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("analysis_id", "topic_id"),
    )
    op.create_index(
        op.f("ix_news_analysis_topics_topic_id"),
        "news_analysis_topics",
        ["topic_id"],
        unique=False,
    )
    op.create_table(
        "news_source_runs",
        sa.Column("id", sa.Integer(), nullable=False, comment="Run ID."),
        sa.Column(
            "source_id", sa.Integer(), nullable=False, comment="Collected source."
        ),
        sa.Column(
            "job_id", sa.Integer(), nullable=True, comment="Owning collection job."
        ),
        sa.Column("status", sa.String(length=20), nullable=False, comment="Run state."),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Start time.",
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Completion time.",
        ),
        sa.Column(
            "new_count", sa.Integer(), nullable=False, comment="Inserted materials."
        ),
        sa.Column(
            "updated_count", sa.Integer(), nullable=False, comment="Changed materials."
        ),
        sa.Column(
            "unchanged_count",
            sa.Integer(),
            nullable=False,
            comment="Unchanged materials.",
        ),
        sa.Column("error", sa.Text(), nullable=True, comment="Safe failure summary."),
        sa.ForeignKeyConstraint(["job_id"], ["news_jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_id"], ["news_sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_news_source_runs_job_id"), "news_source_runs", ["job_id"], unique=False
    )
    op.create_index(
        op.f("ix_news_source_runs_source_id"),
        "news_source_runs",
        ["source_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_news_source_runs_started_at"),
        "news_source_runs",
        ["started_at"],
        unique=False,
    )

    op.create_foreign_key(
        "fk_news_items_latest_analysis",
        "news_items",
        "news_analyses",
        ["latest_analysis_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_news_items_latest_decision",
        "news_items",
        "news_editorial_decisions",
        ["latest_decision_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_news_items_latest_analysis", "news_items", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_news_items_latest_decision", "news_items", type_="foreignkey"
    )
    op.drop_index(op.f("ix_news_source_runs_started_at"), table_name="news_source_runs")
    op.drop_index(op.f("ix_news_source_runs_source_id"), table_name="news_source_runs")
    op.drop_index(op.f("ix_news_source_runs_job_id"), table_name="news_source_runs")
    op.drop_table("news_source_runs")
    op.drop_index(
        op.f("ix_news_analysis_topics_topic_id"), table_name="news_analysis_topics"
    )
    op.drop_table("news_analysis_topics")
    op.drop_index(op.f("ix_news_jobs_source_id"), table_name="news_jobs")
    op.drop_index("ix_news_jobs_queue", table_name="news_jobs")
    op.drop_index(op.f("ix_news_jobs_lease_expires_at"), table_name="news_jobs")
    op.drop_index(op.f("ix_news_jobs_item_id"), table_name="news_jobs")
    op.drop_index(op.f("ix_news_jobs_created_at"), table_name="news_jobs")
    op.drop_table("news_jobs")
    op.drop_index(
        op.f("ix_news_editorial_decisions_item_id"),
        table_name="news_editorial_decisions",
    )
    op.drop_index(
        op.f("ix_news_editorial_decisions_decision"),
        table_name="news_editorial_decisions",
    )
    op.drop_index(
        op.f("ix_news_editorial_decisions_created_at"),
        table_name="news_editorial_decisions",
    )
    op.drop_table("news_editorial_decisions")
    op.drop_index(op.f("ix_news_analyses_news_score"), table_name="news_analyses")
    op.drop_index(op.f("ix_news_analyses_item_id"), table_name="news_analyses")
    op.drop_index(
        "ix_news_analyses_formats", table_name="news_analyses", postgresql_using="gin"
    )
    op.drop_index(op.f("ix_news_analyses_created_at"), table_name="news_analyses")
    op.drop_index(op.f("ix_news_analyses_category_id"), table_name="news_analyses")
    op.drop_index(op.f("ix_news_analyses_article_score"), table_name="news_analyses")
    op.drop_table("news_analyses")
    op.drop_index(
        op.f("ix_news_source_topics_topic_id"), table_name="news_source_topics"
    )
    op.drop_table("news_source_topics")
    op.drop_index(
        op.f("ix_news_source_categories_category_id"),
        table_name="news_source_categories",
    )
    op.drop_table("news_source_categories")
    op.drop_index("ix_news_items_status_seen", table_name="news_items")
    op.drop_index(op.f("ix_news_items_source_id"), table_name="news_items")
    op.drop_index(op.f("ix_news_items_published_at"), table_name="news_items")
    op.drop_index(op.f("ix_news_items_normalized_url"), table_name="news_items")
    op.drop_index(op.f("ix_news_items_latest_analysis_id"), table_name="news_items")
    op.drop_index(op.f("ix_news_items_first_seen_at"), table_name="news_items")
    op.drop_index(op.f("ix_news_items_duplicate_of_id"), table_name="news_items")
    op.drop_table("news_items")
    op.drop_index(op.f("ix_news_topics_active"), table_name="news_topics")
    op.drop_table("news_topics")
    op.drop_index(op.f("ix_news_sources_last_success_at"), table_name="news_sources")
    op.drop_index(op.f("ix_news_sources_active"), table_name="news_sources")
    op.drop_table("news_sources")
    op.drop_table("news_settings")
    op.drop_index(op.f("ix_news_categories_active"), table_name="news_categories")
    op.drop_table("news_categories")
