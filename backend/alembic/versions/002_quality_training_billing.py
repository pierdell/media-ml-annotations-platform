"""Add quality control, training, and billing tables.

Revision ID: 002
Revises: 001
Create Date: 2026-02-18
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Annotation Reviews
    op.create_table(
        "annotation_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("annotation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("annotations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("reviewer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Agreement Scores
    op.create_table(
        "agreement_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("dataset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("dataset_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("dataset_items.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("annotator_ids", postgresql.JSONB, nullable=False),
        sa.Column("metric", sa.String(50), nullable=False),
        sa.Column("score", sa.Float, nullable=False),
        sa.Column("details", postgresql.JSONB, nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_agreement_dataset_item", "agreement_scores", ["dataset_id", "dataset_item_id"])

    # Training Jobs
    op.create_table(
        "training_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("dataset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("datasets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("dataset_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("dataset_versions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("model_type", sa.String(100), nullable=False),
        sa.Column("base_model", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("hyperparameters", postgresql.JSONB, server_default="{}"),
        sa.Column("current_epoch", sa.Integer, server_default="0"),
        sa.Column("total_epochs", sa.Integer, server_default="0"),
        sa.Column("train_loss", sa.Float, nullable=True),
        sa.Column("val_loss", sa.Float, nullable=True),
        sa.Column("metrics", postgresql.JSONB, nullable=True),
        sa.Column("model_path", sa.String(1024), nullable=True),
        sa.Column("export_format", sa.String(50), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_training_project_status", "training_jobs", ["project_id", "status"])

    # Billing: Usage Records (only used when BILLING_ENABLED=true)
    op.create_table(
        "usage_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("usage_type", sa.String(50), nullable=False),
        sa.Column("quantity", sa.Float, nullable=False, server_default="1"),
        sa.Column("unit", sa.String(50), nullable=False, server_default="'count'"),
        sa.Column("metadata_extra", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_usage_project_type_date", "usage_records", ["project_id", "usage_type", "created_at"])

    # Billing: Project Quotas
    op.create_table(
        "project_quotas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("storage_quota_bytes", sa.BigInteger, server_default=str(50 * 1024 * 1024 * 1024)),
        sa.Column("storage_used_bytes", sa.BigInteger, server_default="0"),
        sa.Column("compute_quota_seconds", sa.Float, server_default="360000"),
        sa.Column("compute_used_seconds", sa.Float, server_default="0"),
        sa.Column("api_rate_limit_per_hour", sa.Integer, server_default="1000"),
        sa.Column("api_requests_this_hour", sa.Integer, server_default="0"),
        sa.Column("api_hour_reset_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("max_media_items", sa.Integer, server_default="10000"),
        sa.Column("max_projects", sa.Integer, server_default="10"),
        sa.Column("max_concurrent_training_jobs", sa.Integer, server_default="2"),
        sa.Column("training_gpu_hours_quota", sa.Float, server_default="10"),
        sa.Column("training_gpu_hours_used", sa.Float, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Billing: Subscriptions
    op.create_table(
        "subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("tier", sa.String(20), server_default="'free'"),
        sa.Column("stripe_customer_id", sa.String(255), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("subscriptions")
    op.drop_table("project_quotas")
    op.drop_index("ix_usage_project_type_date")
    op.drop_table("usage_records")
    op.drop_index("ix_training_project_status")
    op.drop_table("training_jobs")
    op.drop_index("ix_agreement_dataset_item")
    op.drop_table("agreement_scores")
    op.drop_table("annotation_reviews")
