from pydantic import BaseModel
import uuid
from datetime import datetime


class DocumentCreate(BaseModel):
    source_type: str  # 'webpage', 'markdown', 'pdf', 'text'
    source_url: str | None = None
    title: str | None = None
    raw_text: str | None = None
    metadata: dict | None = None


class DocumentResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    source_type: str
    source_url: str | None
    title: str | None
    raw_text: str | None
    indexed: bool
    created_at: datetime
    chunk_count: int = 0

    model_config = {"from_attributes": True}


class DocumentChunkResponse(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    chunk_index: int
    content: str
    token_count: int | None
    indexed: bool

    model_config = {"from_attributes": True}


class ReferenceMediaResponse(BaseModel):
    id: uuid.UUID
    object_id: uuid.UUID
    file_name: str
    mime_type: str | None
    file_size: int | None
    indexed: bool
    created_at: datetime

    model_config = {"from_attributes": True}
