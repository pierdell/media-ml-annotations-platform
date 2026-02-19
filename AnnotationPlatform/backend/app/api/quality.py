"""Quality control endpoints - reviews, inter-annotator agreement, approval workflows."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_editor, require_viewer
from app.models.dataset import Annotation, Dataset, DatasetItem
from app.models.quality import AgreementScore, AnnotationReview, ReviewStatus
from app.models.user import User

router = APIRouter(prefix="/projects/{project_id}/quality", tags=["quality"])


# ── Reviews ───────────────────────────────────────────────

@router.post("/reviews", response_model=dict, status_code=201)
async def create_review(
    project_id: uuid.UUID,
    annotation_id: uuid.UUID = Query(...),
    status: str = Query(..., pattern=r"^(approved|rejected|needs_revision)$"),
    comment: str | None = None,
    user: User = Depends(get_current_user),
    project_access: tuple = Depends(require_editor),
    db: AsyncSession = Depends(get_db),
):
    """Create or update a review for an annotation."""
    project, _ = project_access

    # Verify annotation exists
    result = await db.execute(select(Annotation).where(Annotation.id == annotation_id))
    annotation = result.scalar_one_or_none()
    if not annotation:
        raise HTTPException(status_code=404, detail="Annotation not found")

    # Prevent self-review
    if annotation.created_by == user.id:
        raise HTTPException(status_code=400, detail="Cannot review your own annotation")

    review = AnnotationReview(
        annotation_id=annotation_id,
        reviewer_id=user.id,
        status=ReviewStatus(status),
        comment=comment,
    )
    db.add(review)
    await db.commit()

    return {
        "review_id": str(review.id),
        "annotation_id": str(annotation_id),
        "status": status,
        "reviewer_id": str(user.id),
    }


@router.get("/reviews", response_model=dict)
async def list_reviews(
    project_id: uuid.UUID,
    dataset_id: uuid.UUID | None = None,
    status: str | None = Query(default=None, pattern=r"^(pending|approved|rejected|needs_revision)$"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    project_access: tuple = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
):
    """List annotation reviews with optional filtering."""
    project, _ = project_access

    query = select(AnnotationReview)
    if dataset_id:
        query = query.join(Annotation, AnnotationReview.annotation_id == Annotation.id)
        query = query.join(DatasetItem, Annotation.dataset_item_id == DatasetItem.id)
        query = query.where(DatasetItem.dataset_id == dataset_id)
    if status:
        query = query.where(AnnotationReview.status == ReviewStatus(status))

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    query = query.order_by(AnnotationReview.created_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    reviews = result.scalars().all()

    return {
        "items": [
            {
                "id": str(r.id),
                "annotation_id": str(r.annotation_id),
                "reviewer_id": str(r.reviewer_id) if r.reviewer_id else None,
                "status": r.status,
                "comment": r.comment,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in reviews
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


# ── Inter-Annotator Agreement ─────────────────────────────

@router.post("/{dataset_id}/agreement", response_model=dict)
async def compute_agreement(
    project_id: uuid.UUID,
    dataset_id: uuid.UUID,
    metric: str = Query(default="cohens_kappa", pattern=r"^(cohens_kappa|iou|fleiss_kappa|percent_agreement)$"),
    project_access: tuple = Depends(require_editor),
    db: AsyncSession = Depends(get_db),
):
    """
    Compute inter-annotator agreement for a dataset.

    Metrics:
    - cohens_kappa: Cohen's Kappa for 2 annotators
    - iou: Intersection over Union for bounding boxes
    - fleiss_kappa: Fleiss' Kappa for multiple annotators
    - percent_agreement: Simple percentage agreement
    """
    project, _ = project_access

    # Get all annotations grouped by item
    result = await db.execute(
        select(DatasetItem.id, Annotation.created_by, Annotation.label, Annotation.geometry, Annotation.annotation_type)
        .join(Annotation, Annotation.dataset_item_id == DatasetItem.id)
        .where(DatasetItem.dataset_id == dataset_id)
        .order_by(DatasetItem.id)
    )
    rows = result.all()

    if not rows:
        return {"metric": metric, "score": None, "message": "No annotations found", "item_scores": []}

    # Group by item
    item_annotations: dict[str, list] = {}
    for item_id, user_id, label, geometry, ann_type in rows:
        key = str(item_id)
        if key not in item_annotations:
            item_annotations[key] = []
        item_annotations[key].append({
            "user_id": str(user_id) if user_id else "unknown",
            "label": label,
            "geometry": geometry,
            "type": ann_type,
        })

    # Compute agreement per item
    item_scores = []
    all_annotator_ids = set()

    for item_id, annotations in item_annotations.items():
        annotators = {a["user_id"] for a in annotations}
        all_annotator_ids |= annotators

        if len(annotators) < 2:
            continue  # Need at least 2 annotators

        if metric == "iou":
            score = _compute_iou_agreement(annotations)
        elif metric == "percent_agreement":
            score = _compute_percent_agreement(annotations)
        else:
            score = _compute_label_agreement(annotations)

        item_scores.append({
            "item_id": item_id,
            "score": round(score, 4),
            "annotator_count": len(annotators),
        })

        # Store in DB
        agreement = AgreementScore(
            dataset_id=dataset_id,
            dataset_item_id=uuid.UUID(item_id),
            annotator_ids=list(annotators),
            metric=metric,
            score=score,
        )
        db.add(agreement)

    await db.commit()

    avg_score = sum(s["score"] for s in item_scores) / len(item_scores) if item_scores else 0

    return {
        "metric": metric,
        "score": round(avg_score, 4),
        "items_with_multiple_annotators": len(item_scores),
        "total_annotators": len(all_annotator_ids),
        "item_scores": item_scores[:50],  # Limit response size
    }


@router.get("/{dataset_id}/summary", response_model=dict)
async def quality_summary(
    project_id: uuid.UUID,
    dataset_id: uuid.UUID,
    project_access: tuple = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
):
    """Get quality control summary for a dataset."""
    project, _ = project_access

    # Review stats
    review_result = await db.execute(
        select(AnnotationReview.status, func.count())
        .join(Annotation, AnnotationReview.annotation_id == Annotation.id)
        .join(DatasetItem, Annotation.dataset_item_id == DatasetItem.id)
        .where(DatasetItem.dataset_id == dataset_id)
        .group_by(AnnotationReview.status)
    )
    review_stats = {row[0]: row[1] for row in review_result.all()}

    # Latest agreement scores
    agreement_result = await db.execute(
        select(AgreementScore)
        .where(AgreementScore.dataset_id == dataset_id)
        .order_by(AgreementScore.computed_at.desc())
        .limit(1)
    )
    latest_agreement = agreement_result.scalar_one_or_none()

    # Annotation source breakdown
    source_result = await db.execute(
        select(Annotation.source, func.count())
        .join(DatasetItem, Annotation.dataset_item_id == DatasetItem.id)
        .where(DatasetItem.dataset_id == dataset_id)
        .group_by(Annotation.source)
    )
    source_stats = {row[0]: row[1] for row in source_result.all()}

    return {
        "reviews": {
            "approved": review_stats.get(ReviewStatus.APPROVED, 0),
            "rejected": review_stats.get(ReviewStatus.REJECTED, 0),
            "needs_revision": review_stats.get(ReviewStatus.NEEDS_REVISION, 0),
            "pending": review_stats.get(ReviewStatus.PENDING, 0),
        },
        "agreement": {
            "metric": latest_agreement.metric if latest_agreement else None,
            "score": latest_agreement.score if latest_agreement else None,
            "computed_at": latest_agreement.computed_at.isoformat() if latest_agreement and latest_agreement.computed_at else None,
        },
        "annotation_sources": source_stats,
    }


# ── Computation helpers ───────────────────────────────────

def _compute_label_agreement(annotations: list[dict]) -> float:
    """Compute label agreement between annotators."""
    by_user: dict[str, set] = {}
    for a in annotations:
        uid = a["user_id"]
        if uid not in by_user:
            by_user[uid] = set()
        by_user[uid].add(a["label"])

    users = list(by_user.keys())
    if len(users) < 2:
        return 1.0

    agreements = 0
    total = 0
    for i in range(len(users)):
        for j in range(i + 1, len(users)):
            overlap = by_user[users[i]] & by_user[users[j]]
            union = by_user[users[i]] | by_user[users[j]]
            agreements += len(overlap) / max(len(union), 1)
            total += 1

    return agreements / max(total, 1)


def _compute_iou_agreement(annotations: list[dict]) -> float:
    """Compute IoU agreement for bounding box annotations."""
    bboxes_by_user: dict[str, list] = {}
    for a in annotations:
        if a.get("type") != "bbox" or not a.get("geometry"):
            continue
        uid = a["user_id"]
        if uid not in bboxes_by_user:
            bboxes_by_user[uid] = []
        bboxes_by_user[uid].append(a["geometry"])

    users = list(bboxes_by_user.keys())
    if len(users) < 2:
        return 1.0

    total_iou = 0.0
    count = 0
    for i in range(len(users)):
        for j in range(i + 1, len(users)):
            for b1 in bboxes_by_user[users[i]]:
                for b2 in bboxes_by_user[users[j]]:
                    total_iou += _bbox_iou(b1, b2)
                    count += 1

    return total_iou / max(count, 1)


def _compute_percent_agreement(annotations: list[dict]) -> float:
    """Simple percent agreement on labels."""
    by_user: dict[str, list] = {}
    for a in annotations:
        uid = a["user_id"]
        if uid not in by_user:
            by_user[uid] = []
        by_user[uid].append(a["label"])

    users = list(by_user.keys())
    if len(users) < 2:
        return 1.0

    agreements = 0
    total = 0
    for i in range(len(users)):
        for j in range(i + 1, len(users)):
            labels_i = sorted(by_user[users[i]])
            labels_j = sorted(by_user[users[j]])
            if labels_i == labels_j:
                agreements += 1
            total += 1

    return agreements / max(total, 1)


def _bbox_iou(b1: dict, b2: dict) -> float:
    """Calculate Intersection over Union for two bounding boxes."""
    x1 = max(b1.get("x", 0), b2.get("x", 0))
    y1 = max(b1.get("y", 0), b2.get("y", 0))
    x2 = min(b1.get("x", 0) + b1.get("w", 0), b2.get("x", 0) + b2.get("w", 0))
    y2 = min(b1.get("y", 0) + b1.get("h", 0), b2.get("y", 0) + b2.get("h", 0))

    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    area1 = b1.get("w", 0) * b1.get("h", 0)
    area2 = b2.get("w", 0) * b2.get("h", 0)
    union = area1 + area2 - intersection

    return intersection / max(union, 1e-6)
