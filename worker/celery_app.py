"""Celery application configuration."""

import os

from celery import Celery
from celery.signals import worker_init

broker_url = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/1")
result_backend = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")

app = Celery(
    "indexfactory",
    broker=broker_url,
    backend=result_backend,
    include=[
        "worker.tasks.indexing",
        "worker.tasks.embedding",
    ],
)

app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # Timeouts
    task_time_limit=600,       # 10 min hard limit
    task_soft_time_limit=540,  # 9 min soft limit

    # Prefetch
    worker_prefetch_multiplier=1,  # One task at a time per worker process

    # Retry
    task_acks_late=True,
    task_reject_on_worker_lost=True,

    # Task routing
    task_routes={
        "worker.tasks.embedding.run_clip_embedding": {"queue": "embedding"},
        "worker.tasks.embedding.run_dino_embedding": {"queue": "embedding"},
        "worker.tasks.indexing.run_vlm_captioning": {"queue": "vlm"},
        "worker.tasks.indexing.run_text_embedding": {"queue": "default"},
        "worker.tasks.indexing.export_dataset": {"queue": "default"},
    },

    # Beat schedule (periodic tasks)
    beat_schedule={
        "reprocess-failed-media": {
            "task": "worker.tasks.indexing.reprocess_failed",
            "schedule": 300.0,  # Every 5 minutes
        },
    },

    # Results
    result_expires=3600,
)


@worker_init.connect
def on_worker_init(**kwargs):
    """Pre-load ML models on worker startup for faster first inference."""
    import structlog
    logger = structlog.get_logger()
    logger.info("worker_init", pid=os.getpid())
