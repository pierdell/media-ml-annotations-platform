import uuid
import structlog
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    SearchParams,
    models,
)
from app.config import get_settings

logger = structlog.get_logger()
settings = get_settings()

CLIP_DIM = 512  # ViT-B-32
TEXT_DIM = 384   # sentence-transformers all-MiniLM-L6-v2


def get_qdrant_client() -> QdrantClient:
    return QdrantClient(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        api_key=settings.qdrant_api_key,
    )


async def ensure_collections(client: QdrantClient | None = None):
    """Create qdrant collections if they don't exist."""
    c = client or get_qdrant_client()
    existing = {col.name for col in c.get_collections().collections}

    if settings.qdrant_collection_image not in existing:
        c.create_collection(
            collection_name=settings.qdrant_collection_image,
            vectors_config=VectorParams(size=CLIP_DIM, distance=Distance.COSINE),
        )
        logger.info("Created image collection", name=settings.qdrant_collection_image)

    if settings.qdrant_collection_text not in existing:
        c.create_collection(
            collection_name=settings.qdrant_collection_text,
            vectors_config=VectorParams(size=TEXT_DIM, distance=Distance.COSINE),
        )
        logger.info("Created text collection", name=settings.qdrant_collection_text)


def upsert_image_vector(
    point_id: str,
    vector: list[float],
    payload: dict,
    client: QdrantClient | None = None,
):
    c = client or get_qdrant_client()
    c.upsert(
        collection_name=settings.qdrant_collection_image,
        points=[PointStruct(id=point_id, vector=vector, payload=payload)],
    )


def upsert_text_vector(
    point_id: str,
    vector: list[float],
    payload: dict,
    client: QdrantClient | None = None,
):
    c = client or get_qdrant_client()
    c.upsert(
        collection_name=settings.qdrant_collection_text,
        points=[PointStruct(id=point_id, vector=vector, payload=payload)],
    )


def search_images(
    vector: list[float],
    limit: int = 20,
    filter_conditions: dict | None = None,
    client: QdrantClient | None = None,
) -> list[dict]:
    c = client or get_qdrant_client()
    qfilter = _build_filter(filter_conditions) if filter_conditions else None
    results = c.search(
        collection_name=settings.qdrant_collection_image,
        query_vector=vector,
        limit=limit,
        query_filter=qfilter,
        search_params=SearchParams(hnsw_ef=128, exact=False),
    )
    return [{"id": str(r.id), "score": r.score, "payload": r.payload} for r in results]


def search_text(
    vector: list[float],
    limit: int = 20,
    filter_conditions: dict | None = None,
    client: QdrantClient | None = None,
) -> list[dict]:
    c = client or get_qdrant_client()
    qfilter = _build_filter(filter_conditions) if filter_conditions else None
    results = c.search(
        collection_name=settings.qdrant_collection_text,
        query_vector=vector,
        limit=limit,
        query_filter=qfilter,
        search_params=SearchParams(hnsw_ef=128, exact=False),
    )
    return [{"id": str(r.id), "score": r.score, "payload": r.payload} for r in results]


def _build_filter(conditions: dict) -> Filter:
    must = []
    for key, value in conditions.items():
        must.append(FieldCondition(key=key, match=MatchValue(value=value)))
    return Filter(must=must)
