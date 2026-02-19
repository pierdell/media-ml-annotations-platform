"""Billing models - usage records, quotas, subscriptions.

Only created when BILLING_ENABLED=true.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    BigInteger, Boolean, DateTime, Enum, Float, ForeignKey,
    Index, Integer, String, Text, func,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UsageType(StrEnum):
    API_REQUEST = "api_request"
    STORAGE_BYTES = "storage_bytes"
    COMPUTE_SECONDS = "compute_seconds"
    EMBEDDING_GENERATION = "embedding_generation"
    VLM_INFERENCE = "vlm_inference"
    TRAINING_SECONDS = "training_seconds"
    EXPORT = "export"
    AUGMENTATION = "augmentation"


class SubscriptionTier(StrEnum):
    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class UsageRecord(Base):
    """Individual usage event record."""
    __tablename__ = "usage_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    usage_type: Mapped[UsageType] = mapped_column(Enum(UsageType, native_enum=False), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    unit: Mapped[str] = mapped_column(String(50), nullable=False, default="count")
    metadata_extra: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_usage_project_type_date", "project_id", "usage_type", "created_at"),
    )


class ProjectQuota(Base):
    """Per-project resource quotas."""
    __tablename__ = "project_quotas"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, unique=True)

    # Storage
    storage_quota_bytes: Mapped[int] = mapped_column(BigInteger, default=50 * 1024 * 1024 * 1024)  # 50GB
    storage_used_bytes: Mapped[int] = mapped_column(BigInteger, default=0)

    # Compute
    compute_quota_seconds: Mapped[float] = mapped_column(Float, default=360000.0)  # 100 hours
    compute_used_seconds: Mapped[float] = mapped_column(Float, default=0.0)

    # API
    api_rate_limit_per_hour: Mapped[int] = mapped_column(Integer, default=1000)
    api_requests_this_hour: Mapped[int] = mapped_column(Integer, default=0)
    api_hour_reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Media items
    max_media_items: Mapped[int] = mapped_column(Integer, default=10000)
    max_projects: Mapped[int] = mapped_column(Integer, default=10)

    # Training
    max_concurrent_training_jobs: Mapped[int] = mapped_column(Integer, default=2)
    training_gpu_hours_quota: Mapped[float] = mapped_column(Float, default=10.0)
    training_gpu_hours_used: Mapped[float] = mapped_column(Float, default=0.0)

    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Subscription(Base):
    """Project subscription / billing plan."""
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, unique=True)
    tier: Mapped[SubscriptionTier] = mapped_column(Enum(SubscriptionTier, native_enum=False), default=SubscriptionTier.FREE)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    current_period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
