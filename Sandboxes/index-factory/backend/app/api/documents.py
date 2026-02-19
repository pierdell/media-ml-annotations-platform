import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.document import Document, DocumentChunk
from app.schemas.documents import DocumentCreate, DocumentResponse, DocumentChunkResponse
from app.services.auth import get_current_user
from app.services.indexing import enqueue_index_document

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.get("/", response_model=list[DocumentResponse])
async def list_documents(
    source_type: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = select(Document).where(Document.user_id == user.id)
    if source_type:
        q = q.where(Document.source_type == source_type)
    q = q.order_by(Document.created_at.desc())
    result = await db.execute(q)
    docs = result.scalars().all()
    # attach chunk counts
    out = []
    for doc in docs:
        count_q = select(func.count()).select_from(DocumentChunk).where(DocumentChunk.document_id == doc.id)
        count_result = await db.execute(count_q)
        resp = DocumentResponse.model_validate(doc)
        resp.chunk_count = count_result.scalar() or 0
        out.append(resp)
    return out


@router.post("/", response_model=DocumentResponse, status_code=201)
async def create_document(
    body: DocumentCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    doc = Document(
        user_id=user.id,
        source_type=body.source_type,
        source_url=body.source_url,
        title=body.title,
        raw_text=body.raw_text,
        metadata_json=body.metadata or {},
    )
    db.add(doc)
    await db.flush()
    await db.refresh(doc)
    # Dispatch indexing
    enqueue_index_document(doc.id)
    return DocumentResponse.model_validate(doc)


@router.post("/upload", response_model=DocumentResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    content = await file.read()
    text = content.decode("utf-8", errors="replace")
    mime = file.content_type or "text/plain"
    source_type = "pdf" if "pdf" in mime else "markdown" if "markdown" in mime else "text"

    doc = Document(
        user_id=user.id,
        source_type=source_type,
        title=title or file.filename,
        raw_text=text,
        metadata_json={"filename": file.filename, "mime_type": mime, "size": len(content)},
    )
    db.add(doc)
    await db.flush()
    await db.refresh(doc)
    enqueue_index_document(doc.id)
    return DocumentResponse.model_validate(doc)


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Document).where(Document.id == document_id, Document.user_id == user.id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentResponse.model_validate(doc)


@router.get("/{document_id}/chunks", response_model=list[DocumentChunkResponse])
async def list_chunks(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(DocumentChunk).where(DocumentChunk.document_id == document_id).order_by(DocumentChunk.chunk_index)
    )
    return result.scalars().all()


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Document).where(Document.id == document_id, Document.user_id == user.id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    await db.delete(doc)
