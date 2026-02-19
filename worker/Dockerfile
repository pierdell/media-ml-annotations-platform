FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libpq-dev gcc libmagic1 ffmpeg curl && \
    rm -rf /var/lib/apt/lists/*

# Install backend requirements (shared models/services)
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy backend code (shared)
COPY backend/app /app/backend/app

# Copy worker code
COPY worker/ /app/worker/

ENV PYTHONPATH=/app

CMD ["celery", "-A", "worker.celery_app", "worker", \
     "--loglevel=info", \
     "--concurrency=${WORKER_CONCURRENCY:-4}", \
     "--max-tasks-per-child=100", \
     "-Q", "default,indexing,embedding,vlm"]
