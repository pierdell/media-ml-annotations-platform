"""Service layer that dispatches indexing tasks to celery workers."""
import uuid
import structlog
from celery import Celery
from app.config import get_settings

logger = structlog.get_logger()
settings = get_settings()

celery_app = Celery("index_factory", broker=settings.rabbitmq_url, backend=settings.redis_url)


def enqueue_index_image(media_id: uuid.UUID, file_path: str):
    """Queue an image for CLIP embedding + qdrant upsert."""
    celery_app.send_task(
        "worker.tasks.index_image",
        args=[str(media_id), file_path],
        queue="indexing",
    )
    logger.info("Enqueued image indexing", media_id=str(media_id))


def enqueue_index_document(document_id: uuid.UUID):
    """Queue a document for chunking + text embedding + qdrant upsert."""
    celery_app.send_task(
        "worker.tasks.index_document",
        args=[str(document_id)],
        queue="indexing",
    )
    logger.info("Enqueued document indexing", document_id=str(document_id))


def enqueue_auto_categorize(item_id: uuid.UUID, item_type: str, object_id: uuid.UUID):
    """Queue auto-categorization for a newly indexed item."""
    celery_app.send_task(
        "worker.tasks.auto_categorize",
        args=[str(item_id), item_type, str(object_id)],
        queue="indexing",
    )
    logger.info("Enqueued auto-categorize", item_id=str(item_id), item_type=item_type)
