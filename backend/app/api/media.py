"""Media upload and management endpoints."""

import hashlib
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_editor, require_viewer
from app.models.media import IndexingStatus, Media, MediaSource, MediaType
from app.models.project import Project, ProjectRole
from app.models.user import User
from app.schemas.media import MediaBulkAction, MediaOut, MediaSourceCreate, MediaSourceOut, MediaUpdate
from app.services.storage import (
    compute_sha256, delete_media, delete_thumbnail,
    get_media_url, get_thumbnail_url, upload_media, upload_thumbnail,
)

router = APIRouter(prefix="/projects/{project_id}/media", tags=["media"])


def _classify_mime(mime: str) -> MediaType:
    if mime.startswith("image/"):
        return MediaType.IMAGE
    if mime.startswith("video/"):
        return MediaType.VIDEO
    if mime.startswith("audio/"):
        return MediaType.AUDIO
    if mime.startswith("text/"):
        return MediaType.TEXT
    return MediaType.DOCUMENT


def _media_out(m: Media) -> MediaOut:
    thumb_url = get_thumbnail_url(m.thumbnail_path) if m.thumbnail_path else None
    source_count = len(m.sources) if m.sources else 0
    return MediaOut(
        **{c.name: getattr(m, c.name) for c in Media.__table__.columns},
        thumbnail_url=thumb_url,
        source_count=source_count,
    )


@router.post("/upload", response_model=list[MediaOut], status_code=201)
async def upload_files(
    project_id: uuid.UUID,
    files: list[UploadFile] = File(...),
    user: User = Depends(get_current_user),
    project_access: tuple = Depends(require_editor),
    db: AsyncSession = Depends(get_db),
):
    project, _ = project_access
    results = []

    for file in files:
        data = await file.read()
        if len(data) == 0:
            continue

        checksum = compute_sha256(data)
        media_type = _classify_mime(file.content_type or "application/octet-stream")
        media_id = uuid.uuid4()

        # Upload to storage
        storage_path = upload_media(
            project_id=project.id,
            media_id=media_id,
            filename=file.filename or "unnamed",
            data=data,
            content_type=file.content_type or "application/octet-stream",
        )

        # Generate thumbnail for images
        thumbnail_path = None
        if media_type == MediaType.IMAGE:
            try:
                thumbnail_path = _generate_image_thumbnail(project.id, media_id, data)
            except Exception:
                pass  # Thumbnail generation is best-effort

        # Extract dimensions
        width, height, duration, fps = None, None, None, None
        if media_type == MediaType.IMAGE:
            width, height = _get_image_dimensions(data)

        media = Media(
            id=media_id,
            project_id=project.id,
            filename=f"{media_id}{_get_ext(file.filename)}",
            original_filename=file.filename or "unnamed",
            media_type=media_type,
            mime_type=file.content_type or "application/octet-stream",
            file_size=len(data),
            storage_path=storage_path,
            thumbnail_path=thumbnail_path,
            width=width,
            height=height,
            duration_seconds=duration,
            fps=fps,
            checksum_sha256=checksum,
            indexing_status=IndexingStatus.PENDING,
            uploaded_by=user.id,
        )
        db.add(media)
        results.append(media)

    await db.commit()

    # Dispatch indexing asynchronously
    if results:
        try:
            from app.services.indexing import dispatch_indexing
            await dispatch_indexing(db, project.id, media_ids=[m.id for m in results])
        except Exception:
            pass  # Don't fail upload if indexing dispatch fails

    return [_media_out(m) for m in results]


@router.get("", response_model=dict)
async def list_media(
    project_id: uuid.UUID,
    media_type: MediaType | None = None,
    indexing_status: IndexingStatus | None = None,
    tag: str | None = None,
    search: str | None = None,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    project_access: tuple = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
):
    project, _ = project_access
    query = select(Media).where(Media.project_id == project.id)

    if media_type:
        query = query.where(Media.media_type == media_type)
    if indexing_status:
        query = query.where(Media.indexing_status == indexing_status)
    if search:
        query = query.where(
            Media.original_filename.ilike(f"%{search}%")
            | Media.title.ilike(f"%{search}%")
            | Media.auto_caption.ilike(f"%{search}%")
        )

    # Count
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # Sort
    sort_col = getattr(Media, sort_by, Media.created_at)
    query = query.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())

    # Paginate
    query = query.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(query)
    items = result.scalars().all()

    return {
        "items": [_media_out(m) for m in items],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
    }


@router.get("/{media_id}", response_model=MediaOut)
async def get_media_item(
    media_id: uuid.UUID,
    project_access: tuple = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
):
    project, _ = project_access
    result = await db.execute(select(Media).where(Media.id == media_id, Media.project_id == project.id))
    media = result.scalar_one_or_none()
    if not media:
        raise HTTPException(status_code=404, detail="Media not found")
    return _media_out(media)


@router.get("/{media_id}/url")
async def get_media_download_url(
    media_id: uuid.UUID,
    project_access: tuple = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
):
    project, _ = project_access
    result = await db.execute(select(Media).where(Media.id == media_id, Media.project_id == project.id))
    media = result.scalar_one_or_none()
    if not media:
        raise HTTPException(status_code=404, detail="Media not found")
    return {"url": get_media_url(media.storage_path)}


@router.patch("/{media_id}", response_model=MediaOut)
async def update_media_item(
    media_id: uuid.UUID,
    body: MediaUpdate,
    project_access: tuple = Depends(require_editor),
    db: AsyncSession = Depends(get_db),
):
    project, _ = project_access
    result = await db.execute(select(Media).where(Media.id == media_id, Media.project_id == project.id))
    media = result.scalar_one_or_none()
    if not media:
        raise HTTPException(status_code=404, detail="Media not found")

    if body.title is not None:
        media.title = body.title
    if body.description is not None:
        media.description = body.description
    if body.user_tags is not None:
        media.user_tags = body.user_tags
    await db.commit()
    return _media_out(media)


@router.delete("/{media_id}", status_code=204)
async def delete_media_item(
    media_id: uuid.UUID,
    project_access: tuple = Depends(require_editor),
    db: AsyncSession = Depends(get_db),
):
    project, _ = project_access
    result = await db.execute(select(Media).where(Media.id == media_id, Media.project_id == project.id))
    media = result.scalar_one_or_none()
    if not media:
        raise HTTPException(status_code=404, detail="Media not found")

    # Delete from storage
    delete_media(media.storage_path)
    if media.thumbnail_path:
        delete_thumbnail(media.thumbnail_path)

    # Delete from Qdrant
    from app.services.qdrant_service import delete_by_media_id
    try:
        delete_by_media_id(str(media.id))
    except Exception:
        pass

    await db.delete(media)
    await db.commit()


@router.post("/bulk", response_model=dict)
async def bulk_action(
    body: MediaBulkAction,
    project_access: tuple = Depends(require_editor),
    db: AsyncSession = Depends(get_db),
):
    project, _ = project_access
    count = 0

    if body.action == "reindex":
        from app.services.indexing import dispatch_indexing
        result = await dispatch_indexing(db, project.id, media_ids=body.media_ids)
        return {"action": "reindex", **result}

    elif body.action == "delete":
        for mid in body.media_ids:
            result = await db.execute(select(Media).where(Media.id == mid, Media.project_id == project.id))
            media = result.scalar_one_or_none()
            if media:
                delete_media(media.storage_path)
                await db.delete(media)
                count += 1
        await db.commit()

    return {"action": body.action, "affected": count}


# ── Sources ───────────────────────────────────────────────
@router.post("/{media_id}/sources", response_model=MediaSourceOut, status_code=201)
async def add_source(
    media_id: uuid.UUID,
    body: MediaSourceCreate,
    project_access: tuple = Depends(require_editor),
    db: AsyncSession = Depends(get_db),
):
    project, _ = project_access
    result = await db.execute(select(Media).where(Media.id == media_id, Media.project_id == project.id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Media not found")

    content_hash = hashlib.sha256(body.content.encode()).hexdigest() if body.content else None
    source = MediaSource(media_id=media_id, content_hash=content_hash, **body.model_dump())
    db.add(source)
    await db.commit()
    return MediaSourceOut.model_validate(source)


@router.get("/{media_id}/sources", response_model=list[MediaSourceOut])
async def list_sources(
    media_id: uuid.UUID,
    project_access: tuple = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
):
    project, _ = project_access
    result = await db.execute(select(MediaSource).where(MediaSource.media_id == media_id).order_by(MediaSource.created_at))
    return [MediaSourceOut.model_validate(s) for s in result.scalars().all()]


# ── Helpers ───────────────────────────────────────────────
def _get_ext(filename: str | None) -> str:
    if not filename or "." not in filename:
        return ""
    return "." + filename.rsplit(".", 1)[-1].lower()


def _get_image_dimensions(data: bytes) -> tuple[int | None, int | None]:
    try:
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(data))
        return img.width, img.height
    except Exception:
        return None, None


def _generate_image_thumbnail(project_id: uuid.UUID, media_id: uuid.UUID, data: bytes) -> str | None:
    try:
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(data))
        img.thumbnail((320, 320), Image.LANCZOS)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return upload_thumbnail(project_id, media_id, buf.getvalue())
    except Exception:
        return None
