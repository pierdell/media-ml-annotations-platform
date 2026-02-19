from pydantic import BaseModel, field_validator
import uuid
from datetime import datetime

VALID_SOURCE_TYPES = {"text", "webpage", "markdown", "pdf"}


class DocumentCreate(BaseModel):
    source_type: str
    source_url: str | None = None
    title: str | None = None
    raw_text: str | None = None
    metadata: dict | None = None

    @field_validator("source_type")
    @classmethod
    def source_type_valid(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in VALID_SOURCE_TYPES:
            raise ValueError(f"source_type must be one of: {', '.join(sorted(VALID_SOURCE_TYPES))}")
        return v

    @field_validator("title")
    @classmethod
    def title_length(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 512:
            raise ValueError("Title must be at most 512 characters")
        return v


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
