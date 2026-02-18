"""Application configuration via pydantic-settings."""

from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── General ────────────────────────────────────────────
    ENVIRONMENT: str = "production"
    SECRET_KEY: str = "CHANGE-ME"
    ALLOWED_ORIGINS: str = "http://localhost"
    API_V1_PREFIX: str = "/api/v1"

    # ── Auth ───────────────────────────────────────────────
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24h
    ALGORITHM: str = "HS256"
    ADMIN_EMAIL: str = "admin@indexfactory.local"
    ADMIN_PASSWORD: str = "admin"

    # ── Database ───────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://indexfactory:indexfactory@localhost:5432/indexfactory"

    @property
    def sync_database_url(self) -> str:
        return self.DATABASE_URL.replace("+asyncpg", "")

    # ── Redis ──────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Celery ─────────────────────────────────────────────
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # ── Qdrant ─────────────────────────────────────────────
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6334
    QDRANT_API_KEY: str = ""
    QDRANT_COLLECTION_CLIP: str = "clip_embeddings"
    QDRANT_COLLECTION_DINO: str = "dino_embeddings"
    QDRANT_COLLECTION_TEXT: str = "text_embeddings"

    # ── MinIO ──────────────────────────────────────────────
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_SECURE: bool = False
    MINIO_MEDIA_BUCKET: str = "media"
    MINIO_THUMBNAIL_BUCKET: str = "thumbnails"
    MINIO_EXPORT_BUCKET: str = "exports"

    # ── ML Models ──────────────────────────────────────────
    CLIP_MODEL_NAME: str = "ViT-B/32"
    DINO_MODEL_NAME: str = "facebook/dinov2-base"
    VLM_MODEL_NAME: str = "Salesforce/blip2-opt-2.7b"
    TEXT_EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"

    # ── Upload limits ──────────────────────────────────────
    MAX_UPLOAD_SIZE_MB: int = 2048  # 2GB
    ALLOWED_IMAGE_TYPES: str = "image/jpeg,image/png,image/webp,image/gif,image/bmp,image/tiff"
    ALLOWED_VIDEO_TYPES: str = "video/mp4,video/webm,video/quicktime,video/x-msvideo,video/x-matroska"
    ALLOWED_AUDIO_TYPES: str = "audio/mpeg,audio/wav,audio/ogg,audio/flac,audio/aac"

    # ── Feature Flags ─────────────────────────────────────
    BILLING_ENABLED: bool = False  # Enable for remote/SaaS deployment
    RATE_LIMITING_ENABLED: bool = True

    # ── Billing (only used when BILLING_ENABLED=true) ─────
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    DEFAULT_STORAGE_QUOTA_GB: int = 50
    DEFAULT_COMPUTE_QUOTA_HOURS: float = 100.0
    DEFAULT_API_RATE_LIMIT: int = 1000  # requests per hour

    # ── Observability ─────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"  # 'json' or 'console'
    PROMETHEUS_ENABLED: bool = False

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
