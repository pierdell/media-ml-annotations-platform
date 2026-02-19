"""Dataset, dataset items, and annotation models."""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean, DateTime, Enum, Float, ForeignKey,
    Index, Integer, String, Text, func,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DatasetType(StrEnum):
    IMAGE_CLASSIFICATION = "image_classification"
    OBJECT_DETECTION = "object_detection"
    INSTANCE_SEGMENTATION = "instance_segmentation"
    SEMANTIC_SEGMENTATION = "semantic_segmentation"
    IMAGE_CAPTIONING = "image_captioning"
    VIDEO_CLASSIFICATION = "video_classification"
    VIDEO_OBJECT_TRACKING = "video_object_tracking"
    AUDIO_CLASSIFICATION = "audio_classification"
    SPEECH_RECOGNITION = "speech_recognition"
    TEXT_CLASSIFICATION = "text_classification"
    NER = "ner"
    CUSTOM = "custom"


class DatasetStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    FROZEN = "frozen"
    ARCHIVED = "archived"


class AnnotationType(StrEnum):
    BBOX = "bbox"
    POLYGON = "polygon"
    POLYLINE = "polyline"
    POINT = "point"
    MASK = "mask"
    CLASSIFICATION = "classification"
    CAPTION = "caption"
    TRANSCRIPTION = "transcription"
    TEMPORAL_SEGMENT = "temporal_segment"
    CUSTOM = "custom"


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    dataset_type: Mapped[DatasetType] = mapped_column(Enum(DatasetType, native_enum=False), nullable=False)
    status: Mapped[DatasetStatus] = mapped_column(Enum(DatasetStatus, native_enum=False), default=DatasetStatus.DRAFT)

    # Label schema
    label_schema: Mapped[dict] = mapped_column(JSONB, default=dict)
    # e.g. {"labels": [{"id": "person", "name": "Person", "color": "#FF6B6B"}], "attributes": [...]}

    # Split configuration
    split_config: Mapped[dict] = mapped_column(JSONB, default=lambda: {"train": 0.8, "val": 0.1, "test": 0.1})

    # Stats (cached)
    item_count: Mapped[int] = mapped_column(Integer, default=0)
    annotated_count: Mapped[int] = mapped_column(Integer, default=0)

    # Auto-population rules
    auto_populate_rules: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # e.g. {"query": "dogs AND outdoor", "media_types": ["image"], "min_confidence": 0.8}

    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="datasets")
    items: Mapped[list["DatasetItem"]] = relationship(back_populates="dataset", cascade="all, delete-orphan")
    versions: Mapped[list["DatasetVersion"]] = relationship(back_populates="dataset", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_dataset_project_slug", "project_id", "slug", unique=True),
    )


class DatasetItem(Base):
    __tablename__ = "dataset_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    media_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("media.id", ondelete="CASCADE"), nullable=False, index=True)

    split: Mapped[str] = mapped_column(String(20), default="train")  # train / val / test
    priority: Mapped[int] = mapped_column(Integer, default=0)  # Higher = annotate first
    is_annotated: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata_extra: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    assigned_to: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    dataset: Mapped["Dataset"] = relationship(back_populates="items")
    media: Mapped["Media"] = relationship(back_populates="dataset_items")
    annotations: Mapped[list["Annotation"]] = relationship(back_populates="dataset_item", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_dataset_item_unique", "dataset_id", "media_id", unique=True),
    )


class Annotation(Base):
    __tablename__ = "annotations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("dataset_items.id", ondelete="CASCADE"), nullable=False, index=True)
    media_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("media.id", ondelete="CASCADE"), nullable=False, index=True)

    annotation_type: Mapped[AnnotationType] = mapped_column(Enum(AnnotationType, native_enum=False), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)

    # Geometry (flexible JSON)
    geometry: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # bbox:      {"x": 10, "y": 20, "w": 100, "h": 50}
    # polygon:   {"points": [[x,y], ...]}
    # point:     {"x": 100, "y": 200}
    # mask:      {"rle": "...", "size": [h, w]}
    # temporal:  {"start_sec": 1.0, "end_sec": 5.0}
    # caption:   {"text": "A dog playing fetch"}

    # Attributes
    attributes: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # e.g. {"occluded": false, "truncated": true, "difficulty": "hard"}

    # For video: frame info
    frame_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timestamp_sec: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Source: 'manual', 'auto_clip', 'auto_vlm', 'imported'
    source: Mapped[str] = mapped_column(String(50), default="manual")

    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    dataset_item: Mapped["DatasetItem"] = relationship(back_populates="annotations")
    media: Mapped["Media"] = relationship(back_populates="annotations")


class DatasetVersion(Base):
    """Immutable snapshots of a dataset for reproducibility."""
    __tablename__ = "dataset_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    version_tag: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Snapshot of item IDs at time of version creation
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # {"items": [{"item_id": "...", "media_id": "...", "split": "train"}], "stats": {...}}

    item_count: Mapped[int] = mapped_column(Integer, nullable=False)
    export_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    export_format: Mapped[str | None] = mapped_column(String(50), nullable=True)  # 'coco', 'yolo', 'pascal_voc', 'csv'

    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    dataset: Mapped["Dataset"] = relationship(back_populates="versions")

    __table_args__ = (
        Index("ix_version_dataset_tag", "dataset_id", "version_tag", unique=True),
    )


from app.models.project import Project  # noqa: E402
from app.models.media import Media  # noqa: E402
