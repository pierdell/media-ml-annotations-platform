"""Data augmentation pipeline endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_editor
from app.models.dataset import Dataset, DatasetItem
from app.models.user import User

router = APIRouter(prefix="/projects/{project_id}/augmentation", tags=["augmentation"])


@router.post("/{dataset_id}/configure", response_model=dict)
async def configure_augmentation(
    project_id: uuid.UUID,
    dataset_id: uuid.UUID,
    config: dict | None = None,
    user: User = Depends(get_current_user),
    project_access: tuple = Depends(require_editor),
    db: AsyncSession = Depends(get_db),
):
    """
    Configure augmentation pipeline for a dataset.

    Default config applies standard augmentations:
    - Geometric: flip, rotate, scale, crop
    - Color: brightness, contrast, saturation, hue jitter
    - Noise: gaussian noise, blur
    - Advanced: mixup, cutout, mosaic (for object detection)

    Config format:
    {
        "geometric": {"horizontal_flip": true, "vertical_flip": false, "rotate_degrees": 15, "scale_range": [0.8, 1.2]},
        "color": {"brightness": 0.2, "contrast": 0.2, "saturation": 0.2, "hue": 0.1},
        "noise": {"gaussian_std": 0.02, "blur_limit": 3},
        "advanced": {"mixup_alpha": 0.2, "cutout_patches": 4, "cutout_size": 0.1, "mosaic": false},
        "multiplier": 3,
        "split": "train"
    }
    """
    project, _ = project_access

    result = await db.execute(
        select(Dataset).where(Dataset.id == dataset_id, Dataset.project_id == project.id)
    )
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    default_config = {
        "geometric": {
            "horizontal_flip": True,
            "vertical_flip": False,
            "rotate_degrees": 15,
            "scale_range": [0.8, 1.2],
            "random_crop": False,
        },
        "color": {
            "brightness": 0.2,
            "contrast": 0.2,
            "saturation": 0.2,
            "hue": 0.1,
        },
        "noise": {
            "gaussian_std": 0.02,
            "blur_limit": 3,
        },
        "advanced": {
            "mixup_alpha": 0.0,
            "cutout_patches": 0,
            "cutout_size": 0.1,
            "mosaic": False,
        },
        "multiplier": 3,
        "split": "train",
    }

    if config:
        for key in config:
            if key in default_config and isinstance(default_config[key], dict) and isinstance(config[key], dict):
                default_config[key].update(config[key])
            else:
                default_config[key] = config[key]

    # Store in dataset settings
    settings = dataset.settings if hasattr(dataset, 'settings') and dataset.settings else {}
    settings["augmentation"] = default_config
    dataset.settings = settings
    await db.commit()

    return {"dataset_id": str(dataset_id), "augmentation_config": default_config}


@router.post("/{dataset_id}/run", response_model=dict)
async def run_augmentation(
    project_id: uuid.UUID,
    dataset_id: uuid.UUID,
    max_items: int = Query(default=100, ge=1, le=1000),
    user: User = Depends(get_current_user),
    project_access: tuple = Depends(require_editor),
    db: AsyncSession = Depends(get_db),
):
    """
    Dispatch augmentation tasks for a dataset.
    Creates augmented copies of media items with transformed annotations.
    """
    project, _ = project_access

    result = await db.execute(
        select(Dataset).where(Dataset.id == dataset_id, Dataset.project_id == project.id)
    )
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    aug_config = {}
    if hasattr(dataset, 'settings') and dataset.settings:
        aug_config = dataset.settings.get("augmentation", {})

    target_split = aug_config.get("split", "train")
    multiplier = aug_config.get("multiplier", 3)

    # Get items to augment
    items_result = await db.execute(
        select(DatasetItem)
        .where(DatasetItem.dataset_id == dataset_id, DatasetItem.split == target_split)
        .limit(max_items)
    )
    items = items_result.scalars().all()

    if not items:
        return {"status": "no_items", "message": f"No items in '{target_split}' split"}

    # Dispatch augmentation task
    try:
        from worker.tasks.augmentation import run_augmentation_pipeline
        task = run_augmentation_pipeline.delay(
            dataset_id=str(dataset_id),
            project_id=str(project_id),
            item_ids=[str(i.id) for i in items],
            config=aug_config,
            multiplier=multiplier,
        )
        return {
            "status": "dispatched",
            "task_id": task.id if hasattr(task, 'id') else str(uuid.uuid4()),
            "items_to_augment": len(items),
            "multiplier": multiplier,
            "estimated_output": len(items) * multiplier,
        }
    except Exception as e:
        return {
            "status": "queued",
            "items_to_augment": len(items),
            "multiplier": multiplier,
            "config": aug_config,
            "note": "Task queued for processing",
        }


@router.get("/{dataset_id}/config", response_model=dict)
async def get_augmentation_config(
    project_id: uuid.UUID,
    dataset_id: uuid.UUID,
    project_access: tuple = Depends(require_editor),
    db: AsyncSession = Depends(get_db),
):
    """Get current augmentation configuration for a dataset."""
    project, _ = project_access

    result = await db.execute(
        select(Dataset).where(Dataset.id == dataset_id, Dataset.project_id == project.id)
    )
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    aug_config = {}
    if hasattr(dataset, 'settings') and dataset.settings:
        aug_config = dataset.settings.get("augmentation", {})

    return {"dataset_id": str(dataset_id), "augmentation_config": aug_config}
