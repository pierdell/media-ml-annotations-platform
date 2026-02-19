"""Indexing management endpoints."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_editor, require_viewer
from app.schemas.search import IndexingJobCreate, IndexingStatusResponse
from app.services.indexing import dispatch_indexing, get_indexing_stats

router = APIRouter(prefix="/projects/{project_id}/indexing", tags=["indexing"])


@router.post("/run", response_model=dict)
async def trigger_indexing(
    project_id: uuid.UUID,
    body: IndexingJobCreate,
    project_access: tuple = Depends(require_editor),
    db: AsyncSession = Depends(get_db),
):
    """Trigger indexing for specific media items or all pending items."""
    project, _ = project_access
    result = await dispatch_indexing(
        db=db,
        project_id=project.id,
        media_ids=body.media_ids,
        pipelines=body.pipelines,
        custom_prompt_id=body.custom_prompt_id,
        priority=body.priority,
    )
    return result


@router.get("/status", response_model=IndexingStatusResponse)
async def indexing_status(
    project_id: uuid.UUID,
    project_access: tuple = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
):
    """Get indexing statistics for the project."""
    project, _ = project_access
    stats = await get_indexing_stats(db, project.id)
    return IndexingStatusResponse(**stats)
