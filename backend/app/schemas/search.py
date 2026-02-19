"""Search and indexing schemas."""

import uuid
from datetime import datetime
from pydantic import BaseModel, Field

from app.models.media import MediaType


class SearchRequest(BaseModel):
    """Hybrid search across media using text and/or image queries."""
    query: str | None = None  # Text query
    image_url: str | None = None  # URL or media ID for reverse image search
    media_types: list[MediaType] | None = None  # Filter by type
    tags: list[str] | None = None  # Filter by tags
    min_confidence: float = Field(default=0.0, ge=0, le=1)
    use_clip: bool = True
    use_text: bool = True
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class SearchResult(BaseModel):
    media_id: uuid.UUID
    score: float
    media_type: MediaType
    filename: str
    thumbnail_url: str | None
    auto_caption: str | None
    auto_tags: list | None
    width: int | None
    height: int | None
    match_source: str  # 'clip', 'text', 'dino', 'hybrid'


class SearchResponse(BaseModel):
    results: list[SearchResult]
    total: int
    query: str | None
    took_ms: float


class SimilarMediaRequest(BaseModel):
    """Find media similar to a given media item."""
    media_id: uuid.UUID
    method: str = Field(default="clip", pattern=r"^(clip|dino|combined)$")
    limit: int = Field(default=10, ge=1, le=50)


class IndexingJobCreate(BaseModel):
    media_ids: list[uuid.UUID] | None = None  # None = all pending
    pipelines: list[str] = Field(default=["clip", "dino", "vlm", "text"])
    custom_prompt_id: uuid.UUID | None = None
    priority: int = Field(default=0, ge=0, le=10)


class IndexingJobOut(BaseModel):
    job_id: str
    status: str
    total_items: int
    processed_items: int
    failed_items: int
    pipelines: list[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class IndexingStatusResponse(BaseModel):
    total_media: int
    indexed: int
    pending: int
    processing: int
    failed: int
