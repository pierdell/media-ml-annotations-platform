"""Dataset management endpoints."""

import json
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import get_current_user, require_editor, require_viewer
from app.models.dataset import (
    Annotation, Dataset, DatasetItem, DatasetStatus, DatasetVersion,
)
from app.models.media import Media
from app.models.project import ProjectRole
from app.models.user import User
from app.schemas.dataset import (
    AnnotationBulkCreate, AnnotationCreate, AnnotationOut, AnnotationUpdate,
    DatasetCreate, DatasetItemAdd, DatasetItemOut,
    DatasetOut, DatasetUpdate, DatasetVersionCreate, DatasetVersionOut,
)

router = APIRouter(prefix="/projects/{project_id}/datasets", tags=["datasets"])


def _slugify(name: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", name.lower())
    return re.sub(r"[-\s]+", "-", slug).strip("-")


@router.post("", response_model=DatasetOut, status_code=201)
async def create_dataset(
    body: DatasetCreate,
    user: User = Depends(get_current_user),
    project_access: tuple = Depends(require_editor),
    db: AsyncSession = Depends(get_db),
):
    project, _ = project_access
    slug = _slugify(body.name)

    dataset = Dataset(
        project_id=project.id,
        slug=slug,
        created_by=user.id,
        **body.model_dump(),
    )
    db.add(dataset)
    await db.commit()
    return DatasetOut.model_validate(dataset)


@router.get("", response_model=list[DatasetOut])
async def list_datasets(
    project_access: tuple = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
):
    project, _ = project_access
    result = await db.execute(
        select(Dataset).where(Dataset.project_id == project.id).order_by(Dataset.updated_at.desc())
    )
    return [DatasetOut.model_validate(d) for d in result.scalars().all()]


@router.get("/{dataset_id}", response_model=DatasetOut)
async def get_dataset(
    dataset_id: uuid.UUID,
    project_access: tuple = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
):
    project, _ = project_access
    result = await db.execute(
        select(Dataset).where(Dataset.id == dataset_id, Dataset.project_id == project.id)
    )
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return DatasetOut.model_validate(dataset)


@router.patch("/{dataset_id}", response_model=DatasetOut)
async def update_dataset(
    dataset_id: uuid.UUID,
    body: DatasetUpdate,
    project_access: tuple = Depends(require_editor),
    db: AsyncSession = Depends(get_db),
):
    project, _ = project_access
    result = await db.execute(
        select(Dataset).where(Dataset.id == dataset_id, Dataset.project_id == project.id)
    )
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(dataset, field, value)
    await db.commit()
    return DatasetOut.model_validate(dataset)


@router.delete("/{dataset_id}", status_code=204)
async def delete_dataset(
    dataset_id: uuid.UUID,
    project_access: tuple = Depends(require_editor),
    db: AsyncSession = Depends(get_db),
):
    project, _ = project_access
    result = await db.execute(
        select(Dataset).where(Dataset.id == dataset_id, Dataset.project_id == project.id)
    )
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    await db.delete(dataset)
    await db.commit()


# ── Dataset Items ─────────────────────────────────────────
@router.post("/{dataset_id}/items", response_model=dict, status_code=201)
async def add_items(
    dataset_id: uuid.UUID,
    body: DatasetItemAdd,
    project_access: tuple = Depends(require_editor),
    db: AsyncSession = Depends(get_db),
):
    project, _ = project_access
    result = await db.execute(
        select(Dataset).where(Dataset.id == dataset_id, Dataset.project_id == project.id)
    )
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    added = 0
    for media_id in body.media_ids:
        # Verify media exists in project
        m = await db.execute(select(Media.id).where(Media.id == media_id, Media.project_id == project.id))
        if not m.scalar_one_or_none():
            continue

        # Check not already added
        existing = await db.execute(
            select(DatasetItem).where(DatasetItem.dataset_id == dataset_id, DatasetItem.media_id == media_id)
        )
        if existing.scalar_one_or_none():
            continue

        item = DatasetItem(dataset_id=dataset_id, media_id=media_id, split=body.split)
        db.add(item)
        added += 1

    dataset.item_count = dataset.item_count + added
    await db.commit()

    return {"added": added, "total": dataset.item_count}


@router.get("/{dataset_id}/items", response_model=dict)
async def list_items(
    dataset_id: uuid.UUID,
    split: str | None = None,
    is_annotated: bool | None = None,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    project_access: tuple = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
):
    project, _ = project_access
    query = select(DatasetItem).where(DatasetItem.dataset_id == dataset_id)

    if split:
        query = query.where(DatasetItem.split == split)
    if is_annotated is not None:
        query = query.where(DatasetItem.is_annotated == is_annotated)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    query = query.options(selectinload(DatasetItem.media)).offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    items = result.scalars().all()

    return {
        "items": [DatasetItemOut.model_validate(i) for i in items],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


@router.delete("/{dataset_id}/items/{item_id}", status_code=204)
async def remove_item(
    dataset_id: uuid.UUID,
    item_id: uuid.UUID,
    project_access: tuple = Depends(require_editor),
    db: AsyncSession = Depends(get_db),
):
    project, _ = project_access
    result = await db.execute(
        select(DatasetItem).where(DatasetItem.id == item_id, DatasetItem.dataset_id == dataset_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    await db.delete(item)

    # Update count
    await db.execute(
        update(Dataset).where(Dataset.id == dataset_id).values(
            item_count=func.greatest(0, Dataset.item_count - 1)
        )
    )
    await db.commit()


# ── Annotations ───────────────────────────────────────────
@router.post("/{dataset_id}/items/{item_id}/annotations", response_model=AnnotationOut, status_code=201)
async def create_annotation(
    dataset_id: uuid.UUID,
    item_id: uuid.UUID,
    body: AnnotationCreate,
    user: User = Depends(get_current_user),
    project_access: tuple = Depends(require_editor),
    db: AsyncSession = Depends(get_db),
):
    project, _ = project_access
    result = await db.execute(
        select(DatasetItem).where(DatasetItem.id == item_id, DatasetItem.dataset_id == dataset_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    annotation = Annotation(
        dataset_item_id=item_id,
        media_id=item.media_id,
        created_by=user.id,
        **body.model_dump(),
    )
    db.add(annotation)

    # Mark item as annotated
    item.is_annotated = True
    await db.commit()

    return AnnotationOut.model_validate(annotation)


@router.post("/{dataset_id}/items/{item_id}/annotations/bulk", response_model=dict, status_code=201)
async def bulk_create_annotations(
    dataset_id: uuid.UUID,
    item_id: uuid.UUID,
    body: AnnotationBulkCreate,
    user: User = Depends(get_current_user),
    project_access: tuple = Depends(require_editor),
    db: AsyncSession = Depends(get_db),
):
    project, _ = project_access
    result = await db.execute(
        select(DatasetItem).where(DatasetItem.id == item_id, DatasetItem.dataset_id == dataset_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    created = []
    for ann_data in body.annotations:
        annotation = Annotation(
            dataset_item_id=item_id,
            media_id=item.media_id,
            created_by=user.id,
            **ann_data.model_dump(),
        )
        db.add(annotation)
        created.append(annotation)

    item.is_annotated = True
    await db.commit()

    return {"created": len(created)}


@router.get("/{dataset_id}/items/{item_id}/annotations", response_model=list[AnnotationOut])
async def list_annotations(
    dataset_id: uuid.UUID,
    item_id: uuid.UUID,
    project_access: tuple = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Annotation).where(Annotation.dataset_item_id == item_id).order_by(Annotation.created_at)
    )
    return [AnnotationOut.model_validate(a) for a in result.scalars().all()]


@router.delete("/{dataset_id}/annotations/{annotation_id}", status_code=204)
async def delete_annotation(
    annotation_id: uuid.UUID,
    project_access: tuple = Depends(require_editor),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Annotation).where(Annotation.id == annotation_id))
    ann = result.scalar_one_or_none()
    if not ann:
        raise HTTPException(status_code=404, detail="Annotation not found")
    await db.delete(ann)
    await db.commit()


# ── Versions ──────────────────────────────────────────────
@router.post("/{dataset_id}/versions", response_model=DatasetVersionOut, status_code=201)
async def create_version(
    dataset_id: uuid.UUID,
    body: DatasetVersionCreate,
    user: User = Depends(get_current_user),
    project_access: tuple = Depends(require_editor),
    db: AsyncSession = Depends(get_db),
):
    project, _ = project_access
    result = await db.execute(
        select(Dataset).where(Dataset.id == dataset_id, Dataset.project_id == project.id)
    )
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    # Build snapshot
    items_result = await db.execute(select(DatasetItem).where(DatasetItem.dataset_id == dataset_id))
    items = items_result.scalars().all()

    snapshot = {
        "items": [
            {"item_id": str(i.id), "media_id": str(i.media_id), "split": i.split}
            for i in items
        ],
        "stats": {
            "total": len(items),
            "train": sum(1 for i in items if i.split == "train"),
            "val": sum(1 for i in items if i.split == "val"),
            "test": sum(1 for i in items if i.split == "test"),
            "annotated": sum(1 for i in items if i.is_annotated),
        },
    }

    version = DatasetVersion(
        dataset_id=dataset_id,
        version_tag=body.version_tag,
        description=body.description,
        snapshot=snapshot,
        item_count=len(items),
        export_format=body.export_format,
        created_by=user.id,
    )
    db.add(version)
    await db.commit()

    # Trigger export if format specified
    if body.export_format:
        try:
            from worker.tasks.indexing import export_dataset
            export_dataset.delay(
                dataset_id=str(dataset_id),
                version_id=str(version.id),
                export_format=body.export_format,
                project_id=str(project.id),
            )
        except Exception:
            pass

    return DatasetVersionOut.model_validate(version)


@router.get("/{dataset_id}/versions", response_model=list[DatasetVersionOut])
async def list_versions(
    dataset_id: uuid.UUID,
    project_access: tuple = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DatasetVersion)
        .where(DatasetVersion.dataset_id == dataset_id)
        .order_by(DatasetVersion.created_at.desc())
    )
    return [DatasetVersionOut.model_validate(v) for v in result.scalars().all()]
