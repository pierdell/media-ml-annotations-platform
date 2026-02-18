"""Indexing tasks - VLM captioning, text embedding, export, reprocessing."""

import json
import os
import uuid

import structlog
from celery import shared_task

logger = structlog.get_logger()


@shared_task(
    bind=True,
    name="worker.tasks.indexing.run_vlm_captioning",
    max_retries=2,
    default_retry_delay=60,
    acks_late=True,
    time_limit=300,
)
def run_vlm_captioning(
    self,
    media_id: str,
    project_id: str,
    storage_path: str,
    media_type: str,
    custom_prompt_id: str | None = None,
    **kwargs,
):
    """Generate captions and tags using VLM for a media item."""
    from backend.app.ml.vlm_service import get_vlm_service
    from backend.app.services.storage import download_media

    try:
        logger.info("vlm_captioning_start", media_id=media_id)

        if media_type not in ("image",):
            return {"status": "skipped", "media_id": media_id, "reason": "unsupported_type"}

        data = download_media(storage_path)
        vlm = get_vlm_service()

        # Generate caption
        caption = vlm.caption_from_bytes(data)

        # Generate tags
        tags = vlm.tags_from_bytes(data)

        # Run custom prompt if specified
        custom_results = None
        if custom_prompt_id:
            custom_results = _run_custom_prompt(data, custom_prompt_id, vlm)

        # Update DB
        _update_media_vlm(media_id, caption, tags, custom_results)

        # Also create text embedding from caption + tags for hybrid search
        _create_text_embedding_from_caption(media_id, project_id, media_type, caption, tags)

        logger.info("vlm_captioning_done", media_id=media_id, caption_len=len(caption), tags=len(tags))
        return {"status": "ok", "media_id": media_id, "caption": caption, "tags": tags}

    except Exception as exc:
        logger.error("vlm_captioning_error", media_id=media_id, error=str(exc))
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    name="worker.tasks.indexing.run_text_embedding",
    max_retries=3,
    default_retry_delay=15,
    acks_late=True,
)
def run_text_embedding(
    self,
    media_id: str,
    project_id: str,
    storage_path: str,
    media_type: str,
    **kwargs,
):
    """Generate text embeddings for media sources (URLs, documents, etc.)."""
    from backend.app.ml.clip_encoder import get_text_encoder
    from backend.app.services.qdrant_service import upsert_embedding, upsert_embeddings_batch
    from backend.app.config import get_settings

    settings = get_settings()

    try:
        logger.info("text_embedding_start", media_id=media_id)
        encoder = get_text_encoder()

        # Get sources from DB
        sources = _get_media_sources(media_id)

        points = []
        for source in sources:
            text_content = source.get("content") or source.get("title") or ""
            if not text_content.strip():
                continue

            # Chunk long texts
            chunks = _chunk_text(text_content, max_length=512)
            for i, chunk in enumerate(chunks):
                embedding = encoder.encode(chunk)
                point_id = f"text_{media_id}_{source['id']}_{i}"
                points.append((
                    point_id,
                    embedding,
                    {
                        "media_id": media_id,
                        "project_id": project_id,
                        "media_type": media_type,
                        "source_id": source["id"],
                        "source_type": source.get("source_type", "unknown"),
                        "text_preview": chunk[:200],
                    },
                ))

        if points:
            upsert_embeddings_batch(settings.QDRANT_COLLECTION_TEXT, points)
            _update_media_text_embedding(media_id, f"text_{media_id}")

        logger.info("text_embedding_done", media_id=media_id, chunks=len(points))
        return {"status": "ok", "media_id": media_id, "embedded_chunks": len(points)}

    except Exception as exc:
        logger.error("text_embedding_error", media_id=media_id, error=str(exc))
        raise self.retry(exc=exc)


@shared_task(name="worker.tasks.indexing.export_dataset")
def export_dataset(dataset_id: str, version_id: str, export_format: str, project_id: str):
    """Export a dataset version in the specified format."""
    from backend.app.services.storage import upload_export

    try:
        logger.info("export_start", dataset_id=dataset_id, format=export_format)

        data = _get_dataset_export_data(dataset_id, version_id)

        if export_format == "coco":
            export_bytes = _export_coco(data)
        elif export_format == "yolo":
            export_bytes = _export_yolo(data)
        elif export_format == "csv":
            export_bytes = _export_csv(data)
        elif export_format == "jsonl":
            export_bytes = _export_jsonl(data)
        else:
            export_bytes = json.dumps(data, indent=2).encode()

        path = upload_export(
            uuid.UUID(project_id),
            uuid.UUID(dataset_id),
            f"v{version_id[:8]}",
            export_bytes,
            export_format,
        )

        _update_version_export_path(version_id, path)
        logger.info("export_done", dataset_id=dataset_id, path=path)
        return {"status": "ok", "path": path}

    except Exception as exc:
        logger.error("export_error", dataset_id=dataset_id, error=str(exc))
        return {"status": "error", "error": str(exc)}


@shared_task(name="worker.tasks.indexing.reprocess_failed")
def reprocess_failed():
    """Periodic task: re-queue failed indexing jobs."""
    from sqlalchemy import create_engine, select, update
    from sqlalchemy.orm import Session
    from backend.app.models.media import Media, IndexingStatus

    sync_url = os.environ.get("SYNC_DATABASE_URL")
    if not sync_url:
        return

    engine = create_engine(sync_url)
    with Session(engine) as session:
        result = session.execute(
            select(Media.id, Media.project_id, Media.storage_path, Media.media_type)
            .where(Media.indexing_status == IndexingStatus.FAILED)
            .limit(50)
        )
        failed = result.all()

        if failed:
            # Mark as processing
            ids = [f.id for f in failed]
            session.execute(
                update(Media).where(Media.id.in_(ids)).values(indexing_status=IndexingStatus.PROCESSING)
            )
            session.commit()

            # Re-dispatch
            from worker.tasks.embedding import run_clip_embedding
            for f in failed:
                run_clip_embedding.delay(
                    media_id=str(f.id),
                    project_id=str(f.project_id),
                    storage_path=f.storage_path,
                    media_type=f.media_type,
                )

            logger.info("reprocess_failed_dispatched", count=len(failed))

    engine.dispose()


# ── Helper functions ──────────────────────────────────────

def _run_custom_prompt(data: bytes, prompt_id: str, vlm) -> dict:
    """Run a custom indexing prompt."""
    from PIL import Image
    import io
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session
    from backend.app.models.project import IndexingPrompt

    sync_url = os.environ.get("SYNC_DATABASE_URL")
    engine = create_engine(sync_url)

    with Session(engine) as session:
        result = session.execute(select(IndexingPrompt).where(IndexingPrompt.id == uuid.UUID(prompt_id)))
        prompt = result.scalar_one_or_none()

    engine.dispose()

    if not prompt:
        return {}

    image = Image.open(io.BytesIO(data))
    answer = vlm.run_custom_prompt(image, prompt.prompt_template)
    return {"prompt_name": prompt.name, "prompt": prompt.prompt_template, "result": answer}


def _create_text_embedding_from_caption(media_id: str, project_id: str, media_type: str, caption: str, tags: list):
    """Create text embedding from VLM caption for hybrid search."""
    from backend.app.ml.clip_encoder import get_text_encoder
    from backend.app.services.qdrant_service import upsert_embedding
    from backend.app.config import get_settings

    settings = get_settings()
    text = f"{caption}. Tags: {', '.join(tags)}"
    encoder = get_text_encoder()
    embedding = encoder.encode(text)

    point_id = f"caption_{media_id}"
    upsert_embedding(
        collection=settings.QDRANT_COLLECTION_TEXT,
        point_id=point_id,
        vector=embedding,
        payload={
            "media_id": media_id,
            "project_id": project_id,
            "media_type": media_type,
            "source_type": "auto_caption",
            "text_preview": text[:200],
        },
    )


def _update_media_vlm(media_id: str, caption: str, tags: list, custom_results: dict | None):
    """Update media with VLM results."""
    from sqlalchemy import create_engine, update
    from sqlalchemy.orm import Session
    from backend.app.models.media import Media, IndexingStatus

    sync_url = os.environ.get("SYNC_DATABASE_URL")
    engine = create_engine(sync_url)

    values = {
        "auto_caption": caption,
        "auto_tags": tags,
        "indexing_status": IndexingStatus.COMPLETED,
    }
    if custom_results:
        values["custom_indexing_results"] = custom_results

    with Session(engine) as session:
        session.execute(update(Media).where(Media.id == uuid.UUID(media_id)).values(**values))
        session.commit()
    engine.dispose()


def _update_media_text_embedding(media_id: str, embedding_id: str):
    from sqlalchemy import create_engine, update
    from sqlalchemy.orm import Session
    from backend.app.models.media import Media

    sync_url = os.environ.get("SYNC_DATABASE_URL")
    engine = create_engine(sync_url)
    with Session(engine) as session:
        session.execute(update(Media).where(Media.id == uuid.UUID(media_id)).values(text_embedding_id=embedding_id))
        session.commit()
    engine.dispose()


def _update_version_export_path(version_id: str, path: str):
    from sqlalchemy import create_engine, update
    from sqlalchemy.orm import Session
    from backend.app.models.dataset import DatasetVersion

    sync_url = os.environ.get("SYNC_DATABASE_URL")
    engine = create_engine(sync_url)
    with Session(engine) as session:
        session.execute(update(DatasetVersion).where(DatasetVersion.id == uuid.UUID(version_id)).values(export_path=path))
        session.commit()
    engine.dispose()


def _get_media_sources(media_id: str) -> list[dict]:
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session
    from backend.app.models.media import MediaSource

    sync_url = os.environ.get("SYNC_DATABASE_URL")
    engine = create_engine(sync_url)
    with Session(engine) as session:
        result = session.execute(select(MediaSource).where(MediaSource.media_id == uuid.UUID(media_id)))
        sources = [
            {"id": str(s.id), "source_type": s.source_type, "content": s.content, "title": s.title, "url": s.url}
            for s in result.scalars().all()
        ]
    engine.dispose()
    return sources


def _get_dataset_export_data(dataset_id: str, version_id: str) -> dict:
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session
    from backend.app.models.dataset import DatasetVersion, DatasetItem, Annotation, Dataset

    sync_url = os.environ.get("SYNC_DATABASE_URL")
    engine = create_engine(sync_url)
    with Session(engine) as session:
        version = session.execute(select(DatasetVersion).where(DatasetVersion.id == uuid.UUID(version_id))).scalar_one()
        dataset = session.execute(select(Dataset).where(Dataset.id == uuid.UUID(dataset_id))).scalar_one()

        items_data = []
        for item_info in version.snapshot.get("items", []):
            item_id = item_info["item_id"]
            annotations = session.execute(
                select(Annotation).where(Annotation.dataset_item_id == uuid.UUID(item_id))
            ).scalars().all()

            items_data.append({
                "media_id": item_info["media_id"],
                "split": item_info["split"],
                "annotations": [
                    {
                        "type": a.annotation_type,
                        "label": a.label,
                        "confidence": a.confidence,
                        "geometry": a.geometry,
                        "attributes": a.attributes,
                        "frame_number": a.frame_number,
                    }
                    for a in annotations
                ],
            })

    engine.dispose()
    return {
        "dataset": dataset.name,
        "type": dataset.dataset_type,
        "version": version.version_tag,
        "label_schema": dataset.label_schema,
        "items": items_data,
    }


def _chunk_text(text: str, max_length: int = 512) -> list[str]:
    """Split text into chunks at sentence boundaries."""
    if len(text) <= max_length:
        return [text]

    chunks = []
    sentences = text.replace("\n", " ").split(". ")
    current = ""

    for sentence in sentences:
        if len(current) + len(sentence) + 2 > max_length:
            if current:
                chunks.append(current.strip())
            current = sentence
        else:
            current = f"{current}. {sentence}" if current else sentence

    if current.strip():
        chunks.append(current.strip())

    return chunks or [text[:max_length]]


def _export_coco(data: dict) -> bytes:
    """Export in COCO JSON format."""
    coco = {
        "info": {"description": data["dataset"], "version": data["version"]},
        "images": [],
        "annotations": [],
        "categories": [],
    }

    # Build categories from label schema
    labels = data.get("label_schema", {}).get("labels", [])
    cat_map = {}
    for i, label in enumerate(labels):
        cat_id = i + 1
        cat_map[label.get("id", label.get("name", ""))] = cat_id
        coco["categories"].append({"id": cat_id, "name": label.get("name", ""), "supercategory": ""})

    ann_id = 1
    for img_id, item in enumerate(data["items"], 1):
        coco["images"].append({"id": img_id, "file_name": item["media_id"]})
        for ann in item["annotations"]:
            geom = ann["geometry"]
            cat_id = cat_map.get(ann["label"], 0)
            coco_ann = {"id": ann_id, "image_id": img_id, "category_id": cat_id}
            if ann["type"] == "bbox":
                coco_ann["bbox"] = [geom["x"], geom["y"], geom["w"], geom["h"]]
                coco_ann["area"] = geom["w"] * geom["h"]
            elif ann["type"] == "polygon":
                flat = [coord for pt in geom.get("points", []) for coord in pt]
                coco_ann["segmentation"] = [flat]
            coco["annotations"].append(coco_ann)
            ann_id += 1

    return json.dumps(coco, indent=2).encode()


def _export_yolo(data: dict) -> bytes:
    """Export in YOLO format (as zip would need zipfile, return txt for now)."""
    lines = []
    labels = data.get("label_schema", {}).get("labels", [])
    label_map = {l.get("id", l.get("name", "")): i for i, l in enumerate(labels)}

    for item in data["items"]:
        for ann in item["annotations"]:
            if ann["type"] == "bbox":
                geom = ann["geometry"]
                cls_id = label_map.get(ann["label"], 0)
                # YOLO format: class x_center y_center width height (normalized)
                lines.append(f"{item['media_id']}: {cls_id} {geom['x']} {geom['y']} {geom['w']} {geom['h']}")

    return "\n".join(lines).encode()


def _export_csv(data: dict) -> bytes:
    import csv
    import io

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["media_id", "split", "annotation_type", "label", "confidence", "geometry"])

    for item in data["items"]:
        for ann in item["annotations"]:
            writer.writerow([
                item["media_id"], item["split"],
                ann["type"], ann["label"], ann["confidence"],
                json.dumps(ann["geometry"]),
            ])

    return output.getvalue().encode()


def _export_jsonl(data: dict) -> bytes:
    lines = []
    for item in data["items"]:
        lines.append(json.dumps({
            "media_id": item["media_id"],
            "split": item["split"],
            "annotations": item["annotations"],
        }))
    return "\n".join(lines).encode()
