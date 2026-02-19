"""Media schemas."""

import uuid
from datetime import datetime
from pydantic import BaseModel, Field, HttpUrl

from app.models.media import MediaType, IndexingStatus


class MediaOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    filename: str
    original_filename: str
    media_type: MediaType
    mime_type: str
    file_size: int
    thumbnail_url: str | None = None
    width: int | None
    height: int | None
    duration_seconds: float | None
    fps: float | None
    indexing_status: IndexingStatus
    auto_caption: str | None
    auto_tags: list | None
    title: str | None
    description: str | None
    user_tags: list | None
    created_at: datetime
    indexed_at: datetime | None
    source_count: int = 0

    model_config = {"from_attributes": True}


class MediaUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    user_tags: list[str] | None = None


class MediaSourceCreate(BaseModel):
    source_type: str = Field(pattern=r"^(url|webpage|markdown|paper|api)$")
    url: str | None = None
    title: str | None = None
    content: str | None = None
    metadata_extra: dict | None = None


class MediaSourceOut(BaseModel):
    id: uuid.UUID
    media_id: uuid.UUID
    source_type: str
    url: str | None
    title: str | None
    content: str | None
    metadata_extra: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MediaBulkAction(BaseModel):
    media_ids: list[uuid.UUID]
    action: str = Field(pattern=r"^(reindex|delete|add_tag|remove_tag)$")
    params: dict = Field(default_factory=dict)


class MediaListParams(BaseModel):
    """Query parameters for media listing."""
    media_type: MediaType | None = None
    indexing_status: IndexingStatus | None = None
    tag: str | None = None
    search: str | None = None
    sort_by: str = "created_at"
    sort_dir: str = "desc"
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=50, ge=1, le=200)
