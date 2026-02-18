"""Billing service - usage tracking, quota enforcement, metering.

All functions are no-ops when BILLING_ENABLED=false.
"""

import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings

logger = structlog.get_logger()


def is_billing_enabled() -> bool:
    """Check if billing module is active."""
    return get_settings().BILLING_ENABLED


async def record_usage(
    db: AsyncSession,
    project_id: uuid.UUID,
    usage_type: str,
    quantity: float = 1.0,
    unit: str = "count",
    user_id: uuid.UUID | None = None,
    metadata: dict | None = None,
) -> None:
    """Record a usage event. No-op if billing is disabled."""
    if not is_billing_enabled():
        return

    from app.billing.models import UsageRecord, UsageType

    record = UsageRecord(
        project_id=project_id,
        user_id=user_id,
        usage_type=UsageType(usage_type),
        quantity=quantity,
        unit=unit,
        metadata_extra=metadata,
    )
    db.add(record)
    # Don't commit here - let the caller manage the transaction


async def check_quota(
    db: AsyncSession,
    project_id: uuid.UUID,
    usage_type: str,
    quantity: float = 1.0,
) -> tuple[bool, str]:
    """
    Check if a project has sufficient quota for an operation.
    Returns (allowed, reason).
    Always returns (True, "") when billing is disabled.
    """
    if not is_billing_enabled():
        return True, ""

    from app.billing.models import ProjectQuota

    result = await db.execute(
        select(ProjectQuota).where(ProjectQuota.project_id == project_id)
    )
    quota = result.scalar_one_or_none()

    if not quota:
        # No quota record = unlimited (or create default)
        await _ensure_quota(db, project_id)
        return True, ""

    if usage_type == "storage_bytes":
        if quota.storage_used_bytes + quantity > quota.storage_quota_bytes:
            return False, "Storage quota exceeded"

    elif usage_type == "compute_seconds":
        if quota.compute_used_seconds + quantity > quota.compute_quota_seconds:
            return False, "Compute quota exceeded"

    elif usage_type == "api_request":
        now = datetime.now(timezone.utc)
        if quota.api_hour_reset_at and now >= quota.api_hour_reset_at:
            # Reset hourly counter
            quota.api_requests_this_hour = 0
            from datetime import timedelta
            quota.api_hour_reset_at = now + timedelta(hours=1)

        if quota.api_requests_this_hour >= quota.api_rate_limit_per_hour:
            return False, "API rate limit exceeded"

    elif usage_type == "training_seconds":
        if quota.training_gpu_hours_used + (quantity / 3600) > quota.training_gpu_hours_quota:
            return False, "Training GPU hours quota exceeded"

    return True, ""


async def increment_usage(
    db: AsyncSession,
    project_id: uuid.UUID,
    usage_type: str,
    quantity: float = 1.0,
) -> None:
    """Increment usage counters on the quota record. No-op if billing disabled."""
    if not is_billing_enabled():
        return

    from app.billing.models import ProjectQuota

    result = await db.execute(
        select(ProjectQuota).where(ProjectQuota.project_id == project_id)
    )
    quota = result.scalar_one_or_none()
    if not quota:
        return

    if usage_type == "storage_bytes":
        quota.storage_used_bytes = quota.storage_used_bytes + int(quantity)
    elif usage_type == "compute_seconds":
        quota.compute_used_seconds = quota.compute_used_seconds + quantity
    elif usage_type == "api_request":
        quota.api_requests_this_hour = quota.api_requests_this_hour + 1
    elif usage_type == "training_seconds":
        quota.training_gpu_hours_used = quota.training_gpu_hours_used + (quantity / 3600)


async def get_usage_summary(
    db: AsyncSession,
    project_id: uuid.UUID,
) -> dict:
    """Get usage summary for a project."""
    if not is_billing_enabled():
        return {"billing_enabled": False}

    from app.billing.models import ProjectQuota, Subscription, UsageRecord, UsageType

    # Quota
    result = await db.execute(
        select(ProjectQuota).where(ProjectQuota.project_id == project_id)
    )
    quota = result.scalar_one_or_none()

    # Subscription
    sub_result = await db.execute(
        select(Subscription).where(Subscription.project_id == project_id)
    )
    subscription = sub_result.scalar_one_or_none()

    # Recent usage by type
    usage_result = await db.execute(
        select(UsageRecord.usage_type, func.sum(UsageRecord.quantity))
        .where(UsageRecord.project_id == project_id)
        .group_by(UsageRecord.usage_type)
    )
    usage_by_type = {row[0]: row[1] for row in usage_result.all()}

    return {
        "billing_enabled": True,
        "subscription": {
            "tier": subscription.tier if subscription else "free",
            "is_active": subscription.is_active if subscription else True,
        },
        "quotas": {
            "storage": {
                "used_bytes": quota.storage_used_bytes if quota else 0,
                "quota_bytes": quota.storage_quota_bytes if quota else 0,
                "used_pct": round(quota.storage_used_bytes / max(quota.storage_quota_bytes, 1) * 100, 1) if quota else 0,
            },
            "compute": {
                "used_seconds": quota.compute_used_seconds if quota else 0,
                "quota_seconds": quota.compute_quota_seconds if quota else 0,
            },
            "api": {
                "requests_this_hour": quota.api_requests_this_hour if quota else 0,
                "rate_limit_per_hour": quota.api_rate_limit_per_hour if quota else 0,
            },
            "training": {
                "gpu_hours_used": quota.training_gpu_hours_used if quota else 0,
                "gpu_hours_quota": quota.training_gpu_hours_quota if quota else 0,
            },
        },
        "usage_totals": usage_by_type,
    }


async def _ensure_quota(db: AsyncSession, project_id: uuid.UUID):
    """Create a default quota record for a project."""
    from app.billing.models import ProjectQuota
    from datetime import timedelta

    quota = ProjectQuota(
        project_id=project_id,
        api_hour_reset_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db.add(quota)
