from fastapi import APIRouter, Depends
from app.models.user import User
from app.schemas.search import SearchRequest, SearchResponse, SearchResult
from app.services.auth import get_current_user
from app.services.qdrant_service import search_text, search_images, get_qdrant_client

router = APIRouter(prefix="/api/search", tags=["search"])


@router.post("/", response_model=SearchResponse)
async def hybrid_search(
    body: SearchRequest,
    user: User = Depends(get_current_user),
):
    """
    Hybrid search across text embeddings and image (CLIP) embeddings.
    Modes: 'text' (sentence-transformer), 'image' (CLIP), 'hybrid' (both merged).
    """
    results: list[SearchResult] = []
    client = get_qdrant_client()

    filters = {"user_id": str(user.id)}
    if body.object_id:
        filters["object_id"] = str(body.object_id)

    if body.mode in ("text", "hybrid"):
        # Encode text query using sentence-transformers
        text_vector = _encode_text_query(body.query)
        text_hits = search_text(text_vector, limit=body.limit, filter_conditions=filters, client=client)
        for hit in text_hits:
            results.append(SearchResult(
                id=hit["id"],
                score=hit["score"],
                content_type=hit["payload"].get("content_type", "document_chunk"),
                title=hit["payload"].get("title"),
                snippet=hit["payload"].get("snippet", ""),
                source_id=hit["payload"].get("source_id"),
                metadata=hit["payload"],
            ))

    if body.mode in ("image", "hybrid"):
        # Encode text query via CLIP for image search
        image_vector = _encode_clip_query(body.query)
        image_hits = search_images(image_vector, limit=body.limit, filter_conditions=filters, client=client)
        for hit in image_hits:
            results.append(SearchResult(
                id=hit["id"],
                score=hit["score"],
                content_type="reference_media",
                title=hit["payload"].get("file_name"),
                snippet=hit["payload"].get("description", ""),
                source_id=hit["payload"].get("source_id"),
                metadata=hit["payload"],
            ))

    # De-duplicate and sort by score
    seen = set()
    unique = []
    for r in sorted(results, key=lambda x: x.score, reverse=True):
        if r.id not in seen:
            seen.add(r.id)
            unique.append(r)
    unique = unique[: body.limit]

    return SearchResponse(results=unique, total=len(unique), query=body.query, mode=body.mode)


def _encode_text_query(query: str) -> list[float]:
    """Lazy-load sentence-transformers model and encode query."""
    global _text_model
    if "_text_model" not in globals() or _text_model is None:
        from sentence_transformers import SentenceTransformer
        _text_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _text_model.encode(query).tolist()


def _encode_clip_query(query: str) -> list[float]:
    """Lazy-load CLIP model and encode a text query for image search."""
    global _clip_model, _clip_tokenizer
    if "_clip_model" not in globals() or _clip_model is None:
        import open_clip
        _clip_model, _, _ = open_clip.create_model_and_transforms("ViT-B-32", pretrained="openai")
        _clip_tokenizer = open_clip.get_tokenizer("ViT-B-32")
        _clip_model.eval()

    import torch
    tokens = _clip_tokenizer([query])
    with torch.no_grad():
        text_features = _clip_model.encode_text(tokens)
        text_features /= text_features.norm(dim=-1, keepdim=True)
    return text_features[0].tolist()


_text_model = None
_clip_model = None
_clip_tokenizer = None
