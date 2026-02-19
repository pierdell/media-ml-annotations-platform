"""Qdrant vector database service for hybrid search."""

import uuid
from typing import Any

import structlog
from qdrant_client import QdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings

logger = structlog.get_logger()
settings = get_settings()

_client: QdrantClient | None = None

# Embedding dimensions by model
CLIP_DIM = 512       # ViT-B/32
DINO_DIM = 768       # DINOv2-base
TEXT_DIM = 384       # all-MiniLM-L6-v2


def get_qdrant_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
            api_key=settings.QDRANT_API_KEY if settings.QDRANT_API_KEY else None,
            prefer_grpc=True,
            timeout=30,
        )
    return _client


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def ensure_collections() -> None:
    """Create Qdrant collections if they don't exist."""
    client = get_qdrant_client()

    collections = {
        settings.QDRANT_COLLECTION_CLIP: {
            "size": CLIP_DIM,
            "distance": models.Distance.COSINE,
        },
        settings.QDRANT_COLLECTION_DINO: {
            "size": DINO_DIM,
            "distance": models.Distance.COSINE,
        },
        settings.QDRANT_COLLECTION_TEXT: {
            "size": TEXT_DIM,
            "distance": models.Distance.COSINE,
        },
    }

    for name, config in collections.items():
        try:
            client.get_collection(name)
            logger.info("qdrant_collection_exists", collection=name)
        except (UnexpectedResponse, Exception):
            client.create_collection(
                collection_name=name,
                vectors_config=models.VectorParams(
                    size=config["size"],
                    distance=config["distance"],
                ),
                # Enable payload indexing for filtering
                optimizers_config=models.OptimizersConfigDiff(
                    indexing_threshold=10000,
                ),
            )
            # Create payload indexes for fast filtering
            for field in ["project_id", "media_id", "media_type"]:
                client.create_payload_index(
                    collection_name=name,
                    field_name=field,
                    field_schema=models.PayloadSchemaType.KEYWORD,
                )
            logger.info("qdrant_collection_created", collection=name, dim=config["size"])


def upsert_embedding(
    collection: str,
    point_id: str,
    vector: list[float],
    payload: dict[str, Any],
) -> None:
    """Upsert a single vector embedding."""
    client = get_qdrant_client()
    client.upsert(
        collection_name=collection,
        points=[
            models.PointStruct(
                id=point_id,
                vector=vector,
                payload=payload,
            )
        ],
    )


def upsert_embeddings_batch(
    collection: str,
    points: list[tuple[str, list[float], dict]],
) -> None:
    """Batch upsert multiple embeddings."""
    client = get_qdrant_client()
    qdrant_points = [
        models.PointStruct(id=pid, vector=vec, payload=pay)
        for pid, vec, pay in points
    ]
    client.upsert(
        collection_name=collection,
        points=qdrant_points,
    )


def search_similar(
    collection: str,
    query_vector: list[float],
    project_id: str | None = None,
    media_types: list[str] | None = None,
    limit: int = 20,
    offset: int = 0,
    score_threshold: float = 0.0,
) -> list[dict]:
    """Search for similar vectors with optional filtering."""
    client = get_qdrant_client()

    # Build filter
    must_conditions = []
    if project_id:
        must_conditions.append(
            models.FieldCondition(key="project_id", match=models.MatchValue(value=project_id))
        )
    if media_types:
        must_conditions.append(
            models.FieldCondition(key="media_type", match=models.MatchAny(any=media_types))
        )

    query_filter = models.Filter(must=must_conditions) if must_conditions else None

    results = client.search(
        collection_name=collection,
        query_vector=query_vector,
        query_filter=query_filter,
        limit=limit,
        offset=offset,
        score_threshold=score_threshold,
        with_payload=True,
    )

    return [
        {
            "point_id": str(r.id),
            "score": r.score,
            **r.payload,
        }
        for r in results
    ]


def search_by_id(
    collection: str,
    point_id: str,
    project_id: str | None = None,
    limit: int = 10,
) -> list[dict]:
    """Find similar items to an existing point."""
    client = get_qdrant_client()

    must_conditions = []
    if project_id:
        must_conditions.append(
            models.FieldCondition(key="project_id", match=models.MatchValue(value=project_id))
        )

    query_filter = models.Filter(must=must_conditions) if must_conditions else None

    results = client.recommend(
        collection_name=collection,
        positive=[point_id],
        query_filter=query_filter,
        limit=limit,
        with_payload=True,
    )

    return [
        {
            "point_id": str(r.id),
            "score": r.score,
            **r.payload,
        }
        for r in results
    ]


def delete_point(collection: str, point_id: str) -> None:
    """Delete a vector from a collection."""
    client = get_qdrant_client()
    client.delete(
        collection_name=collection,
        points_selector=models.PointIdsList(points=[point_id]),
    )


def delete_by_media_id(media_id: str) -> None:
    """Delete all embeddings for a media item across all collections."""
    client = get_qdrant_client()
    for collection in [
        settings.QDRANT_COLLECTION_CLIP,
        settings.QDRANT_COLLECTION_DINO,
        settings.QDRANT_COLLECTION_TEXT,
    ]:
        try:
            client.delete(
                collection_name=collection,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[models.FieldCondition(key="media_id", match=models.MatchValue(value=media_id))]
                    )
                ),
            )
        except Exception as e:
            logger.warning("qdrant_delete_error", collection=collection, media_id=media_id, error=str(e))
