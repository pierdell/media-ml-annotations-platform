"""MinIO / S3 Object Storage service."""

import hashlib
import io
import uuid
from pathlib import Path

from minio import Minio
from minio.error import S3Error

from app.config import get_settings

settings = get_settings()

_client: Minio | None = None


def get_storage_client() -> Minio:
    global _client
    if _client is None:
        _client = Minio(
            endpoint=settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
    return _client


def _ensure_bucket(client: Minio, bucket: str) -> None:
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)


def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def upload_media(
    project_id: uuid.UUID,
    media_id: uuid.UUID,
    filename: str,
    data: bytes,
    content_type: str,
) -> str:
    """Upload media file to MinIO. Returns the storage path."""
    client = get_storage_client()
    bucket = settings.MINIO_MEDIA_BUCKET
    _ensure_bucket(client, bucket)

    ext = Path(filename).suffix
    storage_path = f"{project_id}/{media_id}{ext}"

    client.put_object(
        bucket,
        storage_path,
        io.BytesIO(data),
        length=len(data),
        content_type=content_type,
    )
    return storage_path


def upload_thumbnail(
    project_id: uuid.UUID,
    media_id: uuid.UUID,
    data: bytes,
    content_type: str = "image/jpeg",
) -> str:
    """Upload thumbnail image. Returns the storage path."""
    client = get_storage_client()
    bucket = settings.MINIO_THUMBNAIL_BUCKET
    _ensure_bucket(client, bucket)

    storage_path = f"{project_id}/{media_id}_thumb.jpg"

    client.put_object(
        bucket,
        storage_path,
        io.BytesIO(data),
        length=len(data),
        content_type=content_type,
    )
    return storage_path


def get_media_url(storage_path: str, expires_hours: int = 24) -> str:
    """Get a pre-signed URL for a media file."""
    from datetime import timedelta
    client = get_storage_client()
    return client.presigned_get_object(
        settings.MINIO_MEDIA_BUCKET,
        storage_path,
        expires=timedelta(hours=expires_hours),
    )


def get_thumbnail_url(storage_path: str) -> str:
    """Get URL for a thumbnail (public bucket)."""
    # Thumbnails bucket is public, so direct URL
    scheme = "https" if settings.MINIO_SECURE else "http"
    return f"{scheme}://{settings.MINIO_ENDPOINT}/{settings.MINIO_THUMBNAIL_BUCKET}/{storage_path}"


def download_media(storage_path: str) -> bytes:
    """Download media file content."""
    client = get_storage_client()
    response = client.get_object(settings.MINIO_MEDIA_BUCKET, storage_path)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def delete_media(storage_path: str) -> None:
    """Delete a media file from storage."""
    client = get_storage_client()
    try:
        client.remove_object(settings.MINIO_MEDIA_BUCKET, storage_path)
    except S3Error:
        pass  # Already deleted


def delete_thumbnail(storage_path: str) -> None:
    """Delete a thumbnail from storage."""
    client = get_storage_client()
    try:
        client.remove_object(settings.MINIO_THUMBNAIL_BUCKET, storage_path)
    except S3Error:
        pass


def upload_export(project_id: uuid.UUID, dataset_id: uuid.UUID, version_tag: str, data: bytes, fmt: str) -> str:
    """Upload a dataset export archive."""
    client = get_storage_client()
    bucket = settings.MINIO_EXPORT_BUCKET
    _ensure_bucket(client, bucket)

    ext = {"coco": "json", "yolo": "zip", "pascal_voc": "zip", "csv": "csv", "jsonl": "jsonl"}.get(fmt, "zip")
    storage_path = f"{project_id}/{dataset_id}/{version_tag}.{ext}"

    client.put_object(
        bucket,
        storage_path,
        io.BytesIO(data),
        length=len(data),
        content_type="application/octet-stream",
    )
    return storage_path
