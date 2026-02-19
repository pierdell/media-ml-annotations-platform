import os
from celery import Celery

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://indexfactory:indexfactory_secret@localhost:5672//")
REDIS_URL = os.getenv("REDIS_URL", "redis://:redis_secret@localhost:6379/1")

app = Celery(
    "index_factory_worker",
    broker=RABBITMQ_URL,
    backend=REDIS_URL,
    include=["tasks.indexing"],
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "worker.tasks.index_image": {"queue": "indexing"},
        "worker.tasks.index_document": {"queue": "indexing"},
        "worker.tasks.auto_categorize": {"queue": "indexing"},
    },
)
