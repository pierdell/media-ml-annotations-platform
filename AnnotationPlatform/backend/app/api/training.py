"""Model training endpoints - train/fine-tune models from annotated datasets."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_editor, require_viewer
from app.models.dataset import Dataset, DatasetVersion
from app.models.training import TrainingJob, TrainingStatus
from app.models.user import User

router = APIRouter(prefix="/projects/{project_id}/training", tags=["training"])


@router.post("/jobs", response_model=dict, status_code=201)
async def create_training_job(
    project_id: uuid.UUID,
    name: str = Query(..., min_length=1, max_length=255),
    dataset_id: uuid.UUID = Query(...),
    model_type: str = Query(..., pattern=r"^(image_classifier|object_detector|clip_finetune|text_classifier|custom)$"),
    base_model: str = Query(default="resnet50"),
    epochs: int = Query(default=50, ge=1, le=1000),
    batch_size: int = Query(default=32, ge=1, le=512),
    learning_rate: float = Query(default=0.001, gt=0),
    export_format: str = Query(default="pytorch", pattern=r"^(pytorch|onnx|torchscript)$"),
    dataset_version_id: uuid.UUID | None = None,
    user: User = Depends(get_current_user),
    project_access: tuple = Depends(require_editor),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new model training job.

    Supported model types:
    - image_classifier: Image classification (ResNet, EfficientNet, ViT)
    - object_detector: Object detection (YOLOv8, Faster R-CNN)
    - clip_finetune: Fine-tune CLIP for domain-specific search
    - text_classifier: Text classification
    - custom: Custom training script
    """
    project, _ = project_access

    # Verify dataset exists
    ds = await db.execute(select(Dataset).where(Dataset.id == dataset_id, Dataset.project_id == project.id))
    dataset = ds.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    base_model_map = {
        "image_classifier": "resnet50",
        "object_detector": "yolov8n",
        "clip_finetune": "ViT-B/32",
        "text_classifier": "distilbert-base-uncased",
        "custom": base_model,
    }

    job = TrainingJob(
        project_id=project.id,
        dataset_id=dataset_id,
        dataset_version_id=dataset_version_id,
        name=name,
        model_type=model_type,
        base_model=base_model_map.get(model_type, base_model),
        status=TrainingStatus.QUEUED,
        total_epochs=epochs,
        hyperparameters={
            "epochs": epochs,
            "batch_size": batch_size,
            "learning_rate": learning_rate,
            "optimizer": "adam",
            "weight_decay": 0.0001,
            "scheduler": "cosine",
        },
        export_format=export_format,
        created_by=user.id,
    )
    db.add(job)
    await db.commit()

    # Dispatch training task
    try:
        from worker.tasks.training import run_training_job
        run_training_job.delay(
            job_id=str(job.id),
            project_id=str(project.id),
            dataset_id=str(dataset_id),
        )
    except Exception:
        pass  # Task will be picked up later

    return {
        "job_id": str(job.id),
        "name": name,
        "model_type": model_type,
        "base_model": job.base_model,
        "status": job.status,
        "hyperparameters": job.hyperparameters,
    }


@router.get("/jobs", response_model=dict)
async def list_training_jobs(
    project_id: uuid.UUID,
    status: str | None = None,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    project_access: tuple = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
):
    """List training jobs for a project."""
    project, _ = project_access

    query = select(TrainingJob).where(TrainingJob.project_id == project.id)
    if status:
        query = query.where(TrainingJob.status == TrainingStatus(status))

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    query = query.order_by(TrainingJob.created_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    jobs = result.scalars().all()

    return {
        "items": [_job_out(j) for j in jobs],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


@router.get("/jobs/{job_id}", response_model=dict)
async def get_training_job(
    project_id: uuid.UUID,
    job_id: uuid.UUID,
    project_access: tuple = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
):
    """Get details of a training job including progress and metrics."""
    project, _ = project_access

    result = await db.execute(
        select(TrainingJob).where(TrainingJob.id == job_id, TrainingJob.project_id == project.id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Training job not found")

    return _job_out(job)


@router.post("/jobs/{job_id}/cancel", response_model=dict)
async def cancel_training_job(
    project_id: uuid.UUID,
    job_id: uuid.UUID,
    project_access: tuple = Depends(require_editor),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a running or queued training job."""
    project, _ = project_access

    result = await db.execute(
        select(TrainingJob).where(TrainingJob.id == job_id, TrainingJob.project_id == project.id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Training job not found")

    if job.status in (TrainingStatus.COMPLETED, TrainingStatus.FAILED, TrainingStatus.CANCELLED):
        raise HTTPException(status_code=400, detail=f"Cannot cancel job in {job.status} status")

    job.status = TrainingStatus.CANCELLED
    await db.commit()

    return {"job_id": str(job.id), "status": "cancelled"}


def _job_out(job: TrainingJob) -> dict:
    progress_pct = round(job.current_epoch / job.total_epochs * 100, 1) if job.total_epochs > 0 else 0
    return {
        "id": str(job.id),
        "project_id": str(job.project_id),
        "dataset_id": str(job.dataset_id) if job.dataset_id else None,
        "name": job.name,
        "model_type": job.model_type,
        "base_model": job.base_model,
        "status": job.status,
        "current_epoch": job.current_epoch,
        "total_epochs": job.total_epochs,
        "progress_pct": progress_pct,
        "train_loss": job.train_loss,
        "val_loss": job.val_loss,
        "metrics": job.metrics,
        "hyperparameters": job.hyperparameters,
        "model_path": job.model_path,
        "export_format": job.export_format,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }
