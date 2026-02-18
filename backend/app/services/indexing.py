"""Indexing orchestration service - dispatches ML tasks to Celery workers."""

import uuid
from datetime import datetime, timezone

import structlog
from celery import group
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.media import IndexingStatus, Media

logger = structlog.get_logger()
settings = get_settings()


async def dispatch_indexing(
    db: AsyncSession,
    project_id: uuid.UUID,
    media_ids: list[uuid.UUID] | None = None,
    pipelines: list[str] | None = None,
    custom_prompt_id: uuid.UUID | None = None,
    priority: int = 0,
) -> dict:
    """Dispatch indexing jobs for media items."""
    from worker.tasks.embedding import run_clip_embedding, run_dino_embedding
    from worker.tasks.indexing import run_vlm_captioning, run_text_embedding

    if pipelines is None:
        pipelines = ["clip", "dino", "vlm", "text"]

    # Get media items to process
    query = select(Media).where(Media.project_id == project_id)
    if media_ids:
        query = query.where(Media.id.in_(media_ids))
    else:
        query = query.where(Media.indexing_status.in_([IndexingStatus.PENDING, IndexingStatus.FAILED]))

    result = await db.execute(query)
    items = result.scalars().all()

    if not items:
        return {"job_id": None, "total_items": 0, "message": "No items to index"}

    # Mark as processing
    item_ids = [item.id for item in items]
    await db.execute(
        update(Media)
        .where(Media.id.in_(item_ids))
        .values(indexing_status=IndexingStatus.PROCESSING)
    )
    await db.commit()

    # Build task chains for each media item
    task_pipeline_map = {
        "clip": run_clip_embedding,
        "dino": run_dino_embedding,
        "vlm": run_vlm_captioning,
        "text": run_text_embedding,
    }

    tasks = []
    for item in items:
        for pipeline_name in pipelines:
            task_func = task_pipeline_map.get(pipeline_name)
            if task_func:
                kwargs = {
                    "media_id": str(item.id),
                    "project_id": str(project_id),
                    "storage_path": item.storage_path,
                    "media_type": item.media_type,
                }
                if pipeline_name == "vlm" and custom_prompt_id:
                    kwargs["custom_prompt_id"] = str(custom_prompt_id)

                # Route GPU-heavy tasks to gpu queue if available
                queue = "gpu" if pipeline_name in ("clip", "dino", "vlm") else "default"
                tasks.append(task_func.s(**kwargs).set(queue=queue, priority=priority))

    # Execute as a group (parallel per-item, serial per-pipeline)
    job = group(tasks)
    async_result = job.apply_async()

    job_id = async_result.id if hasattr(async_result, "id") else str(uuid.uuid4())

    logger.info(
        "indexing_dispatched",
        job_id=job_id,
        total_items=len(items),
        pipelines=pipelines,
        total_tasks=len(tasks),
    )

    return {
        "job_id": job_id,
        "total_items": len(items),
        "pipelines": pipelines,
        "total_tasks": len(tasks),
        "status": "dispatched",
    }


async def get_indexing_stats(db: AsyncSession, project_id: uuid.UUID) -> dict:
    """Get indexing statistics for a project."""
    result = await db.execute(
        select(Media.indexing_status, func.count(Media.id))
        .where(Media.project_id == project_id)
        .group_by(Media.indexing_status)
    )
    stats = {row[0]: row[1] for row in result.all()}
    total = sum(stats.values())
    return {
        "total_media": total,
        "indexed": stats.get(IndexingStatus.COMPLETED, 0),
        "pending": stats.get(IndexingStatus.PENDING, 0),
        "processing": stats.get(IndexingStatus.PROCESSING, 0),
        "failed": stats.get(IndexingStatus.FAILED, 0),
        "partial": stats.get(IndexingStatus.PARTIAL, 0),
    }


async def mark_media_indexed(
    db: AsyncSession,
    media_id: uuid.UUID,
    status: IndexingStatus = IndexingStatus.COMPLETED,
    **kwargs,
) -> None:
    """Update a media item's indexing status and metadata."""
    values = {"indexing_status": status}
    if status == IndexingStatus.COMPLETED:
        values["indexed_at"] = datetime.now(timezone.utc)
    values.update({k: v for k, v in kwargs.items() if v is not None})

    await db.execute(update(Media).where(Media.id == media_id).values(**values))
    await db.commit()
