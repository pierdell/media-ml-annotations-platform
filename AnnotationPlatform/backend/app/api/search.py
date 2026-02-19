"""Search endpoints - hybrid search across media using Qdrant."""

import time
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_viewer
from app.models.media import Media
from app.models.user import User
from app.schemas.search import SearchRequest, SearchResponse, SearchResult, SimilarMediaRequest
from app.services.qdrant_service import search_by_id, search_similar
from app.services.storage import get_thumbnail_url
from app.config import get_settings

settings = get_settings()

router = APIRouter(prefix="/projects/{project_id}/search", tags=["search"])


@router.post("", response_model=SearchResponse)
async def search_media(
    project_id: uuid.UUID,
    body: SearchRequest,
    project_access: tuple = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
):
    """
    Hybrid search across media using text query and/or image reference.

    - Text query → encoded via sentence-transformers → searched in text_embeddings + CLIP text encoder
    - Image reference → CLIP/DINO embedding → searched in clip_embeddings / dino_embeddings
    - Results are merged and ranked by score
    """
    project, _ = project_access
    start = time.monotonic()

    if not body.query and not body.image_url:
        raise HTTPException(status_code=400, detail="Provide either query text or image_url")

    all_results = {}
    project_id_str = str(project_id)
    media_type_strs = [mt.value for mt in body.media_types] if body.media_types else None

    # Text search via CLIP text encoding
    if body.query and body.use_clip:
        try:
            text_vector = _encode_text_clip(body.query)
            clip_results = search_similar(
                collection=settings.QDRANT_COLLECTION_CLIP,
                query_vector=text_vector,
                project_id=project_id_str,
                media_types=media_type_strs,
                limit=body.limit * 2,
                score_threshold=body.min_confidence,
            )
            for r in clip_results:
                mid = r.get("media_id")
                if mid not in all_results or r["score"] > all_results[mid]["score"]:
                    all_results[mid] = {**r, "match_source": "clip"}
        except Exception:
            pass  # CLIP not available, fall through

    # Text search via text embeddings (source content, captions)
    if body.query and body.use_text:
        try:
            text_vector = _encode_text_sentence(body.query)
            text_results = search_similar(
                collection=settings.QDRANT_COLLECTION_TEXT,
                query_vector=text_vector,
                project_id=project_id_str,
                media_types=media_type_strs,
                limit=body.limit * 2,
                score_threshold=body.min_confidence,
            )
            for r in text_results:
                mid = r.get("media_id")
                if mid not in all_results or r["score"] > all_results[mid]["score"]:
                    all_results[mid] = {**r, "match_source": "text"}
                elif mid in all_results:
                    # Hybrid: boost score if found in both
                    all_results[mid]["score"] = max(all_results[mid]["score"], r["score"]) * 1.1
                    all_results[mid]["match_source"] = "hybrid"
        except Exception:
            pass

    # Image-based search (reverse image search)
    if body.image_url:
        try:
            # Check if image_url is a media ID (UUID format)
            try:
                ref_media_id = uuid.UUID(body.image_url)
                result = await db.execute(select(Media).where(Media.id == ref_media_id))
                ref_media = result.scalar_one_or_none()
                if ref_media and ref_media.clip_embedding_id:
                    img_results = search_by_id(
                        collection=settings.QDRANT_COLLECTION_CLIP,
                        point_id=ref_media.clip_embedding_id,
                        project_id=project_id_str,
                        limit=body.limit,
                    )
                    for r in img_results:
                        mid = r.get("media_id")
                        if mid != str(ref_media_id):
                            if mid not in all_results or r["score"] > all_results[mid]["score"]:
                                all_results[mid] = {**r, "match_source": "clip"}
            except ValueError:
                # It's a URL, encode the image
                image_vector = await _encode_image_from_url(body.image_url)
                if image_vector:
                    img_results = search_similar(
                        collection=settings.QDRANT_COLLECTION_CLIP,
                        query_vector=image_vector,
                        project_id=project_id_str,
                        media_types=media_type_strs,
                        limit=body.limit,
                    )
                    for r in img_results:
                        mid = r.get("media_id")
                        if mid not in all_results or r["score"] > all_results[mid]["score"]:
                            all_results[mid] = {**r, "match_source": "clip"}
        except Exception:
            pass

    # Sort by score and limit
    sorted_results = sorted(all_results.values(), key=lambda x: x["score"], reverse=True)
    sorted_results = sorted_results[body.offset:body.offset + body.limit]

    # Enrich with DB metadata
    search_results = []
    for r in sorted_results:
        mid = r.get("media_id")
        if not mid:
            continue
        try:
            result = await db.execute(select(Media).where(Media.id == uuid.UUID(mid)))
            media = result.scalar_one_or_none()
            if media:
                search_results.append(SearchResult(
                    media_id=media.id,
                    score=r["score"],
                    media_type=media.media_type,
                    filename=media.original_filename,
                    thumbnail_url=get_thumbnail_url(media.thumbnail_path) if media.thumbnail_path else None,
                    auto_caption=media.auto_caption,
                    auto_tags=media.auto_tags,
                    width=media.width,
                    height=media.height,
                    match_source=r.get("match_source", "unknown"),
                ))
        except Exception:
            continue

    elapsed_ms = (time.monotonic() - start) * 1000

    return SearchResponse(
        results=search_results,
        total=len(all_results),
        query=body.query,
        took_ms=round(elapsed_ms, 1),
    )


@router.post("/similar", response_model=SearchResponse)
async def find_similar(
    project_id: uuid.UUID,
    body: SimilarMediaRequest,
    project_access: tuple = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
):
    """Find media items similar to a given media item."""
    project, _ = project_access
    start = time.monotonic()

    result = await db.execute(select(Media).where(Media.id == body.media_id, Media.project_id == project_id))
    media = result.scalar_one_or_none()
    if not media:
        raise HTTPException(status_code=404, detail="Media not found")

    collection_map = {
        "clip": (settings.QDRANT_COLLECTION_CLIP, media.clip_embedding_id),
        "dino": (settings.QDRANT_COLLECTION_DINO, media.dino_embedding_id),
    }

    if body.method == "combined":
        # Search both and merge
        all_results = {}
        for method_name in ["clip", "dino"]:
            coll, eid = collection_map.get(method_name, (None, None))
            if coll and eid:
                results = search_by_id(coll, eid, str(project_id), body.limit)
                for r in results:
                    mid = r.get("media_id")
                    if mid and mid != str(body.media_id):
                        if mid not in all_results:
                            all_results[mid] = r
                        else:
                            all_results[mid]["score"] = (all_results[mid]["score"] + r["score"]) / 2
        sorted_results = sorted(all_results.values(), key=lambda x: x["score"], reverse=True)[:body.limit]
    else:
        coll, eid = collection_map.get(body.method, (None, None))
        if not coll or not eid:
            raise HTTPException(status_code=400, detail=f"No {body.method} embedding for this media")
        sorted_results = search_by_id(coll, eid, str(project_id), body.limit)
        sorted_results = [r for r in sorted_results if r.get("media_id") != str(body.media_id)]

    # Enrich
    search_results = []
    for r in sorted_results:
        mid = r.get("media_id")
        if not mid:
            continue
        try:
            res = await db.execute(select(Media).where(Media.id == uuid.UUID(mid)))
            m = res.scalar_one_or_none()
            if m:
                search_results.append(SearchResult(
                    media_id=m.id,
                    score=r["score"],
                    media_type=m.media_type,
                    filename=m.original_filename,
                    thumbnail_url=get_thumbnail_url(m.thumbnail_path) if m.thumbnail_path else None,
                    auto_caption=m.auto_caption,
                    auto_tags=m.auto_tags,
                    width=m.width,
                    height=m.height,
                    match_source=body.method,
                ))
        except Exception:
            continue

    elapsed_ms = (time.monotonic() - start) * 1000
    return SearchResponse(results=search_results, total=len(search_results), query=None, took_ms=round(elapsed_ms, 1))


# ── ML encoding helpers (lazy loaded) ─────────────────────
_clip_model = None
_text_model = None


def _encode_text_clip(text: str) -> list[float]:
    global _clip_model
    if _clip_model is None:
        from app.ml.clip_encoder import CLIPEncoder
        _clip_model = CLIPEncoder()
    return _clip_model.encode_text(text)


def _encode_text_sentence(text: str) -> list[float]:
    global _text_model
    if _text_model is None:
        from app.ml.clip_encoder import TextEncoder
        _text_model = TextEncoder()
    return _text_model.encode(text)


async def _encode_image_from_url(url: str) -> list[float] | None:
    try:
        import aiohttp
        from PIL import Image
        import io

        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return None
                data = await resp.read()

        img = Image.open(io.BytesIO(data))
        global _clip_model
        if _clip_model is None:
            from app.ml.clip_encoder import CLIPEncoder
            _clip_model = CLIPEncoder()
        return _clip_model.encode_image(img)
    except Exception:
        return None
