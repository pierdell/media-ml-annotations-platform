"""Data augmentation tasks."""

import io
import json
import uuid

import structlog
from celery import shared_task

logger = structlog.get_logger()


@shared_task(
    bind=True,
    name="worker.tasks.augmentation.run_augmentation_pipeline",
    max_retries=2,
    default_retry_delay=60,
    acks_late=True,
    time_limit=600,
)
def run_augmentation_pipeline(
    self,
    dataset_id: str,
    project_id: str,
    item_ids: list[str],
    config: dict,
    multiplier: int = 3,
    **kwargs,
):
    """
    Run data augmentation pipeline on dataset items.

    For each item, generates `multiplier` augmented copies with
    transformed images and correspondingly adjusted annotations.
    """
    try:
        logger.info("augmentation_start", dataset_id=dataset_id, items=len(item_ids), multiplier=multiplier)

        augmented_count = 0

        for item_id in item_ids:
            item_data = _get_item_data(item_id)
            if not item_data:
                continue

            for i in range(multiplier):
                augmented = _apply_augmentations(item_data, config, seed=hash(f"{item_id}_{i}"))
                if augmented:
                    _save_augmented_item(dataset_id, project_id, item_data, augmented, i)
                    augmented_count += 1

        logger.info("augmentation_done", dataset_id=dataset_id, augmented=augmented_count)
        return {"status": "ok", "augmented_count": augmented_count}

    except Exception as exc:
        logger.error("augmentation_error", dataset_id=dataset_id, error=str(exc))
        raise self.retry(exc=exc)


def _get_item_data(item_id: str) -> dict | None:
    """Load item data including media and annotations."""
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session
    import os

    sync_url = os.environ.get("SYNC_DATABASE_URL")
    if not sync_url:
        return None

    engine = create_engine(sync_url)
    from backend.app.models.dataset import DatasetItem, Annotation
    from backend.app.models.media import Media

    with Session(engine) as session:
        item = session.execute(select(DatasetItem).where(DatasetItem.id == uuid.UUID(item_id))).scalar_one_or_none()
        if not item:
            engine.dispose()
            return None

        media = session.execute(select(Media).where(Media.id == item.media_id)).scalar_one_or_none()
        annotations = session.execute(
            select(Annotation).where(Annotation.dataset_item_id == item.id)
        ).scalars().all()

        data = {
            "item_id": str(item.id),
            "media_id": str(item.media_id),
            "storage_path": media.storage_path if media else "",
            "width": media.width if media else None,
            "height": media.height if media else None,
            "annotations": [
                {
                    "type": a.annotation_type,
                    "label": a.label,
                    "confidence": a.confidence,
                    "geometry": a.geometry,
                }
                for a in annotations
            ],
        }

    engine.dispose()
    return data


def _apply_augmentations(item_data: dict, config: dict, seed: int) -> dict | None:
    """Apply augmentation transforms to an item and its annotations."""
    import random
    random.seed(seed)

    width = item_data.get("width") or 640
    height = item_data.get("height") or 480

    geo = config.get("geometric", {})
    color = config.get("color", {})
    noise = config.get("noise", {})

    # Build transform record
    transforms = []

    if geo.get("horizontal_flip") and random.random() > 0.5:
        transforms.append({"type": "horizontal_flip"})

    if geo.get("vertical_flip") and random.random() > 0.5:
        transforms.append({"type": "vertical_flip"})

    if geo.get("rotate_degrees"):
        angle = random.uniform(-geo["rotate_degrees"], geo["rotate_degrees"])
        transforms.append({"type": "rotate", "angle": angle})

    if geo.get("scale_range"):
        scale = random.uniform(geo["scale_range"][0], geo["scale_range"][1])
        transforms.append({"type": "scale", "factor": scale})

    if color.get("brightness"):
        transforms.append({"type": "brightness", "factor": 1.0 + random.uniform(-color["brightness"], color["brightness"])})

    if color.get("contrast"):
        transforms.append({"type": "contrast", "factor": 1.0 + random.uniform(-color["contrast"], color["contrast"])})

    # Transform annotations
    augmented_annotations = []
    for ann in item_data.get("annotations", []):
        transformed_geom = _transform_geometry(ann["geometry"], ann["type"], transforms, width, height)
        augmented_annotations.append({
            **ann,
            "geometry": transformed_geom,
        })

    return {
        "transforms": transforms,
        "annotations": augmented_annotations,
    }


def _transform_geometry(geometry: dict, ann_type: str, transforms: list, width: int, height: int) -> dict:
    """Apply geometric transforms to annotation geometry."""
    geom = dict(geometry)

    for t in transforms:
        if t["type"] == "horizontal_flip":
            if ann_type == "bbox" and "x" in geom and "w" in geom:
                geom["x"] = width - geom["x"] - geom["w"]
            elif ann_type == "point" and "x" in geom:
                geom["x"] = width - geom["x"]
            elif ann_type == "polygon" and "points" in geom:
                geom["points"] = [[width - p[0], p[1]] for p in geom["points"]]

        elif t["type"] == "vertical_flip":
            if ann_type == "bbox" and "y" in geom and "h" in geom:
                geom["y"] = height - geom["y"] - geom["h"]
            elif ann_type == "point" and "y" in geom:
                geom["y"] = height - geom["y"]
            elif ann_type == "polygon" and "points" in geom:
                geom["points"] = [[p[0], height - p[1]] for p in geom["points"]]

        elif t["type"] == "scale":
            factor = t["factor"]
            if ann_type == "bbox":
                for k in ("x", "y", "w", "h"):
                    if k in geom:
                        geom[k] = geom[k] * factor
            elif ann_type == "point":
                if "x" in geom:
                    geom["x"] = geom["x"] * factor
                if "y" in geom:
                    geom["y"] = geom["y"] * factor
            elif ann_type == "polygon" and "points" in geom:
                geom["points"] = [[p[0] * factor, p[1] * factor] for p in geom["points"]]

    return geom


def _save_augmented_item(dataset_id: str, project_id: str, original: dict, augmented: dict, index: int):
    """Save augmented item metadata to database."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    import os

    sync_url = os.environ.get("SYNC_DATABASE_URL")
    if not sync_url:
        return

    engine = create_engine(sync_url)
    from backend.app.models.dataset import DatasetItem, Annotation

    with Session(engine) as session:
        # Create augmented dataset item referencing original media
        aug_item = DatasetItem(
            dataset_id=uuid.UUID(dataset_id),
            media_id=uuid.UUID(original["media_id"]),
            split="train",
            is_annotated=len(augmented["annotations"]) > 0,
            metadata_extra={
                "augmented": True,
                "source_item_id": original["item_id"],
                "augmentation_index": index,
                "transforms": augmented["transforms"],
            },
        )
        session.add(aug_item)
        session.flush()

        for ann in augmented["annotations"]:
            aug_ann = Annotation(
                dataset_item_id=aug_item.id,
                media_id=uuid.UUID(original["media_id"]),
                annotation_type=ann["type"],
                label=ann["label"],
                confidence=ann["confidence"],
                geometry=ann["geometry"],
                source="augmented",
            )
            session.add(aug_ann)

        session.commit()
    engine.dispose()
