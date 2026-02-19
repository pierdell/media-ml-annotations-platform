"""Embedding generation tasks - CLIP and DINO."""

import uuid

import structlog
from celery import shared_task

logger = structlog.get_logger()


@shared_task(
    bind=True,
    name="worker.tasks.embedding.run_clip_embedding",
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
def run_clip_embedding(self, media_id: str, project_id: str, storage_path: str, media_type: str, **kwargs):
    """Generate CLIP embedding for a media item and store in Qdrant."""
    from backend.app.ml.clip_encoder import get_clip_encoder
    from backend.app.services.storage import download_media
    from backend.app.services.qdrant_service import upsert_embedding
    from backend.app.config import get_settings

    settings = get_settings()

    try:
        logger.info("clip_embedding_start", media_id=media_id)

        # Download media from MinIO
        data = download_media(storage_path)

        # Generate embedding
        encoder = get_clip_encoder()

        if media_type in ("image",):
            embedding = encoder.encode_image_bytes(data)
        elif media_type == "video":
            # For video, extract a keyframe (middle frame) and embed it
            embedding = _embed_video_frame(encoder, data)
        else:
            logger.info("clip_skip_unsupported", media_id=media_id, media_type=media_type)
            return {"status": "skipped", "media_id": media_id, "reason": "unsupported_type"}

        # Store in Qdrant
        point_id = f"clip_{media_id}"
        upsert_embedding(
            collection=settings.QDRANT_COLLECTION_CLIP,
            point_id=point_id,
            vector=embedding,
            payload={
                "media_id": media_id,
                "project_id": project_id,
                "media_type": media_type,
            },
        )

        # Update DB
        _update_media_embedding(media_id, clip_embedding_id=point_id)

        logger.info("clip_embedding_done", media_id=media_id)
        return {"status": "ok", "media_id": media_id, "embedding_id": point_id}

    except Exception as exc:
        logger.error("clip_embedding_error", media_id=media_id, error=str(exc))
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    name="worker.tasks.embedding.run_dino_embedding",
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
def run_dino_embedding(self, media_id: str, project_id: str, storage_path: str, media_type: str, **kwargs):
    """Generate DINOv2 embedding for a media item."""
    from backend.app.ml.dino_encoder import get_dino_encoder
    from backend.app.services.storage import download_media
    from backend.app.services.qdrant_service import upsert_embedding
    from backend.app.config import get_settings

    settings = get_settings()

    try:
        logger.info("dino_embedding_start", media_id=media_id)

        if media_type not in ("image",):
            return {"status": "skipped", "media_id": media_id, "reason": "unsupported_type"}

        data = download_media(storage_path)
        encoder = get_dino_encoder()
        embedding = encoder.encode_image_bytes(data)

        point_id = f"dino_{media_id}"
        upsert_embedding(
            collection=settings.QDRANT_COLLECTION_DINO,
            point_id=point_id,
            vector=embedding,
            payload={
                "media_id": media_id,
                "project_id": project_id,
                "media_type": media_type,
            },
        )

        _update_media_embedding(media_id, dino_embedding_id=point_id)

        logger.info("dino_embedding_done", media_id=media_id)
        return {"status": "ok", "media_id": media_id, "embedding_id": point_id}

    except Exception as exc:
        logger.error("dino_embedding_error", media_id=media_id, error=str(exc))
        raise self.retry(exc=exc)


def _embed_video_frame(encoder, video_data: bytes) -> list[float]:
    """Extract middle frame from video and generate CLIP embedding."""
    import tempfile
    import subprocess
    import io
    from PIL import Image

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=True) as tmp:
        tmp.write(video_data)
        tmp.flush()

        # Use ffmpeg to extract middle frame
        result = subprocess.run(
            [
                "ffmpeg", "-i", tmp.name,
                "-vf", "select=eq(n\\,0)", "-frames:v", "1",
                "-f", "image2pipe", "-vcodec", "png", "-"
            ],
            capture_output=True, timeout=30,
        )

        if result.returncode == 0 and result.stdout:
            image = Image.open(io.BytesIO(result.stdout))
            return encoder.encode_image(image)

    raise ValueError("Failed to extract video frame")


def _update_media_embedding(media_id: str, **kwargs):
    """Update media record with embedding IDs (sync DB call for worker)."""
    import os
    from sqlalchemy import create_engine, update
    from sqlalchemy.orm import Session

    sync_url = os.environ.get("SYNC_DATABASE_URL")
    if not sync_url:
        from backend.app.config import get_settings
        sync_url = get_settings().sync_database_url

    engine = create_engine(sync_url)
    from backend.app.models.media import Media

    with Session(engine) as session:
        session.execute(
            update(Media).where(Media.id == uuid.UUID(media_id)).values(**kwargs)
        )
        session.commit()
    engine.dispose()
