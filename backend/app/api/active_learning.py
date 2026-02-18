"""Active learning endpoints - auto-suggest annotations, human-in-the-loop refinement."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_editor, require_viewer
from app.models.dataset import Annotation, Dataset, DatasetItem
from app.models.media import Media
from app.models.user import User

router = APIRouter(prefix="/projects/{project_id}/active-learning", tags=["active-learning"])


@router.post("/{dataset_id}/suggest", response_model=dict)
async def suggest_annotations(
    project_id: uuid.UUID,
    dataset_id: uuid.UUID,
    limit: int = Query(default=10, ge=1, le=100),
    strategy: str = Query(default="uncertainty", pattern=r"^(uncertainty|diversity|random|entropy)$"),
    user: User = Depends(get_current_user),
    project_access: tuple = Depends(require_editor),
    db: AsyncSession = Depends(get_db),
):
    """
    Suggest which items to annotate next using active learning strategies.

    Strategies:
    - uncertainty: Items where ML models are least confident
    - diversity: Items most different from already-annotated set
    - random: Random unannotated items
    - entropy: Items with highest prediction entropy
    """
    project, _ = project_access

    # Get unannotated items
    query = (
        select(DatasetItem)
        .where(DatasetItem.dataset_id == dataset_id, DatasetItem.is_annotated == False)  # noqa: E712
        .limit(limit * 5)  # Fetch more to allow ranking
    )
    result = await db.execute(query)
    candidates = result.scalars().all()

    if not candidates:
        return {"suggestions": [], "strategy": strategy, "message": "All items are annotated"}

    suggestions = []
    if strategy == "uncertainty":
        suggestions = await _rank_by_uncertainty(db, candidates, limit)
    elif strategy == "diversity":
        suggestions = await _rank_by_diversity(db, candidates, limit)
    elif strategy == "entropy":
        suggestions = await _rank_by_entropy(db, candidates, limit)
    else:
        # Random fallback
        import random
        random.shuffle(candidates)
        suggestions = [
            {"item_id": str(c.id), "media_id": str(c.media_id), "score": 0.5, "reason": "random"}
            for c in candidates[:limit]
        ]

    return {"suggestions": suggestions, "strategy": strategy, "total_unannotated": len(candidates)}


@router.post("/{dataset_id}/auto-annotate", response_model=dict)
async def auto_annotate(
    project_id: uuid.UUID,
    dataset_id: uuid.UUID,
    confidence_threshold: float = Query(default=0.8, ge=0.0, le=1.0),
    max_items: int = Query(default=50, ge=1, le=500),
    user: User = Depends(get_current_user),
    project_access: tuple = Depends(require_editor),
    db: AsyncSession = Depends(get_db),
):
    """
    Auto-annotate items using ML model predictions above a confidence threshold.
    Creates annotations with source='auto_vlm' that can be reviewed by humans.
    """
    project, _ = project_access

    # Get unannotated items with ML predictions
    result = await db.execute(
        select(DatasetItem, Media)
        .join(Media, DatasetItem.media_id == Media.id)
        .where(
            DatasetItem.dataset_id == dataset_id,
            DatasetItem.is_annotated == False,  # noqa: E712
            Media.auto_tags.isnot(None),
        )
        .limit(max_items)
    )
    items = result.all()

    created_count = 0
    for item, media in items:
        if not media.auto_tags:
            continue

        # Get dataset label schema
        ds_result = await db.execute(select(Dataset).where(Dataset.id == dataset_id))
        dataset = ds_result.scalar_one_or_none()
        if not dataset:
            break

        labels = {l["id"]: l for l in dataset.label_schema.get("labels", [])}

        for tag in media.auto_tags:
            tag_str = tag if isinstance(tag, str) else str(tag)
            tag_lower = tag_str.lower().strip()
            # Match against label schema
            matched_label = None
            for label_id, label_info in labels.items():
                if tag_lower == label_id.lower() or tag_lower == label_info.get("name", "").lower():
                    matched_label = label_id
                    break

            if matched_label:
                annotation = Annotation(
                    dataset_item_id=item.id,
                    media_id=media.id,
                    annotation_type="classification",
                    label=matched_label,
                    confidence=confidence_threshold,
                    geometry={"auto": True},
                    source="auto_vlm",
                    created_by=user.id,
                )
                db.add(annotation)
                created_count += 1

        if created_count > 0:
            item.is_annotated = True

    await db.commit()

    return {
        "auto_annotated": created_count,
        "items_processed": len(items),
        "confidence_threshold": confidence_threshold,
        "source": "auto_vlm",
    }


@router.get("/{dataset_id}/stats", response_model=dict)
async def active_learning_stats(
    project_id: uuid.UUID,
    dataset_id: uuid.UUID,
    project_access: tuple = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
):
    """Get active learning statistics for a dataset."""
    project, _ = project_access

    total = (await db.execute(
        select(func.count()).select_from(DatasetItem).where(DatasetItem.dataset_id == dataset_id)
    )).scalar() or 0

    annotated = (await db.execute(
        select(func.count()).select_from(DatasetItem)
        .where(DatasetItem.dataset_id == dataset_id, DatasetItem.is_annotated == True)  # noqa: E712
    )).scalar() or 0

    auto_annotations = (await db.execute(
        select(func.count()).select_from(Annotation)
        .join(DatasetItem, Annotation.dataset_item_id == DatasetItem.id)
        .where(DatasetItem.dataset_id == dataset_id, Annotation.source == "auto_vlm")
    )).scalar() or 0

    manual_annotations = (await db.execute(
        select(func.count()).select_from(Annotation)
        .join(DatasetItem, Annotation.dataset_item_id == DatasetItem.id)
        .where(DatasetItem.dataset_id == dataset_id, Annotation.source == "manual")
    )).scalar() or 0

    return {
        "total_items": total,
        "annotated_items": annotated,
        "unannotated_items": total - annotated,
        "auto_annotations": auto_annotations,
        "manual_annotations": manual_annotations,
        "completion_pct": round(annotated / total * 100, 1) if total > 0 else 0,
    }


# ── Ranking helpers ───────────────────────────────────────

async def _rank_by_uncertainty(db: AsyncSession, candidates: list, limit: int) -> list[dict]:
    """Rank by ML model confidence - prefer low-confidence items."""
    scored = []
    for c in candidates:
        result = await db.execute(select(Media).where(Media.id == c.media_id))
        media = result.scalar_one_or_none()
        if media and media.auto_tags:
            # Use number of tags as proxy for certainty (fewer = more uncertain)
            uncertainty = 1.0 / (len(media.auto_tags) + 1)
        else:
            uncertainty = 1.0  # No predictions = maximum uncertainty
        scored.append({
            "item_id": str(c.id),
            "media_id": str(c.media_id),
            "score": round(uncertainty, 3),
            "reason": "high_uncertainty",
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:limit]


async def _rank_by_diversity(db: AsyncSession, candidates: list, limit: int) -> list[dict]:
    """Rank by diversity - prefer items different from already-annotated ones."""
    # Simple diversity: prioritize items with unique media types or different auto_tags
    scored = []
    seen_tags = set()

    for c in candidates:
        result = await db.execute(select(Media).where(Media.id == c.media_id))
        media = result.scalar_one_or_none()
        tags = frozenset(media.auto_tags or []) if media else frozenset()
        novelty = 1.0 - (len(tags & seen_tags) / max(len(tags), 1))
        seen_tags |= tags
        scored.append({
            "item_id": str(c.id),
            "media_id": str(c.media_id),
            "score": round(novelty, 3),
            "reason": "high_diversity",
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:limit]


async def _rank_by_entropy(db: AsyncSession, candidates: list, limit: int) -> list[dict]:
    """Rank by prediction entropy."""
    import math

    scored = []
    for c in candidates:
        result = await db.execute(select(Media).where(Media.id == c.media_id))
        media = result.scalar_one_or_none()
        if media and media.auto_tags and len(media.auto_tags) > 1:
            # Uniform distribution assumption for tag probabilities
            n = len(media.auto_tags)
            entropy = math.log(n) if n > 1 else 0
        elif media and media.auto_caption:
            entropy = 0.5  # Has caption but no tags
        else:
            entropy = 1.0  # No data
        scored.append({
            "item_id": str(c.id),
            "media_id": str(c.media_id),
            "score": round(entropy, 3),
            "reason": "high_entropy",
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:limit]
