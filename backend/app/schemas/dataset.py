"""Dataset & Annotation schemas."""

import uuid
from datetime import datetime
from pydantic import BaseModel, Field

from app.models.dataset import DatasetType, DatasetStatus, AnnotationType


class DatasetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    dataset_type: DatasetType
    label_schema: dict = Field(default_factory=lambda: {"labels": [], "attributes": []})
    split_config: dict = Field(default_factory=lambda: {"train": 0.8, "val": 0.1, "test": 0.1})
    auto_populate_rules: dict | None = None


class DatasetUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: DatasetStatus | None = None
    label_schema: dict | None = None
    split_config: dict | None = None
    auto_populate_rules: dict | None = None


class DatasetOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    slug: str
    description: str | None
    dataset_type: DatasetType
    status: DatasetStatus
    label_schema: dict
    split_config: dict
    item_count: int
    annotated_count: int
    auto_populate_rules: dict | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DatasetItemAdd(BaseModel):
    media_ids: list[uuid.UUID]
    split: str = "train"


class DatasetItemOut(BaseModel):
    id: uuid.UUID
    dataset_id: uuid.UUID
    media_id: uuid.UUID
    split: str
    priority: int
    is_annotated: bool
    assigned_to: uuid.UUID | None
    created_at: datetime
    # Nested media info
    media: "MediaItemSummary | None" = None

    model_config = {"from_attributes": True}


class MediaItemSummary(BaseModel):
    id: uuid.UUID
    filename: str
    media_type: str
    thumbnail_url: str | None = None
    width: int | None
    height: int | None

    model_config = {"from_attributes": True}


class AnnotationCreate(BaseModel):
    annotation_type: AnnotationType
    label: str = Field(min_length=1, max_length=255)
    confidence: float = Field(default=1.0, ge=0, le=1)
    geometry: dict
    attributes: dict | None = None
    frame_number: int | None = None
    timestamp_sec: float | None = None
    source: str = "manual"


class AnnotationUpdate(BaseModel):
    label: str | None = None
    confidence: float | None = None
    geometry: dict | None = None
    attributes: dict | None = None


class AnnotationOut(BaseModel):
    id: uuid.UUID
    dataset_item_id: uuid.UUID
    media_id: uuid.UUID
    annotation_type: AnnotationType
    label: str
    confidence: float
    geometry: dict
    attributes: dict | None
    frame_number: int | None
    timestamp_sec: float | None
    source: str
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AnnotationBulkCreate(BaseModel):
    annotations: list[AnnotationCreate]


class DatasetVersionCreate(BaseModel):
    version_tag: str = Field(min_length=1, max_length=50, pattern=r"^[a-zA-Z0-9._-]+$")
    description: str | None = None
    export_format: str | None = Field(default=None, pattern=r"^(coco|yolo|pascal_voc|csv|jsonl)$")


class DatasetVersionOut(BaseModel):
    id: uuid.UUID
    dataset_id: uuid.UUID
    version_tag: str
    description: str | None
    item_count: int
    export_path: str | None
    export_format: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
