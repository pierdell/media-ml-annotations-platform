import os
import uuid
import aiofiles
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.config import get_settings
from app.models.user import User
from app.models.object import Object
from app.models.reference_media import ReferenceMedia
from app.schemas.documents import ReferenceMediaResponse
from app.services.auth import get_current_user
from app.services.indexing import enqueue_index_image

router = APIRouter(prefix="/api/media", tags=["media"])
settings = get_settings()


@router.get("/{object_id}", response_model=list[ReferenceMediaResponse])
async def list_media(
    object_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # verify ownership
    obj_r = await db.execute(select(Object).where(Object.id == object_id, Object.user_id == user.id))
    if not obj_r.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Object not found")
    result = await db.execute(
        select(ReferenceMedia).where(ReferenceMedia.object_id == object_id).order_by(ReferenceMedia.created_at.desc())
    )
    return result.scalars().all()


@router.post("/{object_id}/upload", response_model=ReferenceMediaResponse, status_code=201)
async def upload_media(
    object_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    obj_r = await db.execute(select(Object).where(Object.id == object_id, Object.user_id == user.id))
    if not obj_r.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Object not found")

    upload_dir = os.path.join(settings.upload_dir, str(object_id))
    os.makedirs(upload_dir, exist_ok=True)

    file_id = uuid.uuid4()
    ext = os.path.splitext(file.filename or "")[1]
    file_path = os.path.join(upload_dir, f"{file_id}{ext}")

    content = await file.read()
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)

    media = ReferenceMedia(
        object_id=object_id,
        file_path=file_path,
        file_name=file.filename or str(file_id),
        mime_type=file.content_type,
        file_size=len(content),
    )
    db.add(media)
    await db.flush()
    await db.refresh(media)

    enqueue_index_image(media.id, file_path)
    return media


@router.delete("/{object_id}/{media_id}", status_code=204)
async def delete_media(
    object_id: uuid.UUID,
    media_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ReferenceMedia).where(ReferenceMedia.id == media_id, ReferenceMedia.object_id == object_id)
    )
    media = result.scalar_one_or_none()
    if not media:
        raise HTTPException(status_code=404, detail="Media not found")
    if os.path.exists(media.file_path):
        os.remove(media.file_path)
    await db.delete(media)
