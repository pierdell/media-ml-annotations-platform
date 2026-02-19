from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://indexfactory:indexfactory_secret@localhost:5432/indexfactory"
    database_url_sync: str = "postgresql://indexfactory:indexfactory_secret@localhost:5432/indexfactory"

    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_api_key: str = "qdrant_secret"
    qdrant_collection_text: str = "text_embeddings"
    qdrant_collection_image: str = "image_embeddings"

    # RabbitMQ
    rabbitmq_url: str = "amqp://indexfactory:indexfactory_secret@localhost:5672//"

    # Redis
    redis_url: str = "redis://:redis_secret@localhost:6379/0"

    # Auth
    secret_key: str = "change-me-in-production-please"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440  # 24 h

    # CLIP
    clip_model_name: str = "ViT-B-32"
    clip_pretrained: str = "openai"

    # Upload
    upload_dir: str = "/app/uploads"
    max_upload_size: int = 100 * 1024 * 1024  # 100 MB

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
