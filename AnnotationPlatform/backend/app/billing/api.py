"""Billing API endpoints.

Only registered when BILLING_ENABLED=true.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_admin, require_viewer
from app.models.user import User
from app.billing.service import get_usage_summary, is_billing_enabled

router = APIRouter(prefix="/projects/{project_id}/billing", tags=["billing"])


@router.get("/usage", response_model=dict)
async def get_project_usage(
    project_id: uuid.UUID,
    project_access: tuple = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
):
    """Get usage summary and quota status for a project."""
    project, _ = project_access
    return await get_usage_summary(db, project.id)


@router.get("/usage/history", response_model=dict)
async def get_usage_history(
    project_id: uuid.UUID,
    usage_type: str | None = None,
    days: int = Query(default=30, ge=1, le=365),
    project_access: tuple = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
):
    """Get usage history over time."""
    project, _ = project_access

    if not is_billing_enabled():
        return {"billing_enabled": False, "history": []}

    from app.billing.models import UsageRecord
    from datetime import datetime, timezone, timedelta

    since = datetime.now(timezone.utc) - timedelta(days=days)

    query = (
        select(
            func.date_trunc("day", UsageRecord.created_at).label("day"),
            UsageRecord.usage_type,
            func.sum(UsageRecord.quantity).label("total"),
        )
        .where(UsageRecord.project_id == project.id, UsageRecord.created_at >= since)
        .group_by("day", UsageRecord.usage_type)
        .order_by("day")
    )

    if usage_type:
        query = query.where(UsageRecord.usage_type == usage_type)

    result = await db.execute(query)
    rows = result.all()

    history = [
        {
            "date": row[0].isoformat() if row[0] else None,
            "usage_type": row[1],
            "total": row[2],
        }
        for row in rows
    ]

    return {"billing_enabled": True, "history": history}


@router.post("/quotas", response_model=dict)
async def update_quotas(
    project_id: uuid.UUID,
    storage_quota_gb: int | None = None,
    compute_quota_hours: float | None = None,
    api_rate_limit: int | None = None,
    training_gpu_hours: float | None = None,
    project_access: tuple = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update project quotas (admin only)."""
    project, _ = project_access

    if not is_billing_enabled():
        raise HTTPException(status_code=400, detail="Billing is not enabled")

    from app.billing.models import ProjectQuota

    result = await db.execute(
        select(ProjectQuota).where(ProjectQuota.project_id == project.id)
    )
    quota = result.scalar_one_or_none()

    if not quota:
        quota = ProjectQuota(project_id=project.id)
        db.add(quota)

    if storage_quota_gb is not None:
        quota.storage_quota_bytes = storage_quota_gb * 1024 * 1024 * 1024
    if compute_quota_hours is not None:
        quota.compute_quota_seconds = compute_quota_hours * 3600
    if api_rate_limit is not None:
        quota.api_rate_limit_per_hour = api_rate_limit
    if training_gpu_hours is not None:
        quota.training_gpu_hours_quota = training_gpu_hours

    await db.commit()

    return {
        "storage_quota_gb": quota.storage_quota_bytes / (1024 * 1024 * 1024),
        "compute_quota_hours": quota.compute_quota_seconds / 3600,
        "api_rate_limit_per_hour": quota.api_rate_limit_per_hour,
        "training_gpu_hours": quota.training_gpu_hours_quota,
    }
