"""Media, source/reference, and embedding models."""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    BigInteger, Boolean, DateTime, Enum, Float, ForeignKey,
    Index, Integer, String, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MediaType(StrEnum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    TEXT = "text"
    DOCUMENT = "document"


class IndexingStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


class Media(Base):
    __tablename__ = "media"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)

    # File info
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    media_type: Mapped[MediaType] = mapped_column(Enum(MediaType, native_enum=False), nullable=False, index=True)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    thumbnail_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    # Media metadata
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    fps: Mapped[float | None] = mapped_column(Float, nullable=True)
    codec: Mapped[str | None] = mapped_column(String(64), nullable=True)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # ML indexing
    indexing_status: Mapped[IndexingStatus] = mapped_column(
        Enum(IndexingStatus, native_enum=False), default=IndexingStatus.PENDING, index=True
    )
    clip_embedding_id: Mapped[str | None] = mapped_column(String(128), nullable=True)  # Qdrant point ID
    dino_embedding_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    text_embedding_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # VLM-generated descriptions
    auto_caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    auto_tags: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    custom_indexing_results: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # User-provided metadata
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_tags: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    metadata_extra: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Timestamps
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="media_items")
    sources: Mapped[list["MediaSource"]] = relationship(back_populates="media", cascade="all, delete-orphan")
    dataset_items: Mapped[list["DatasetItem"]] = relationship(back_populates="media", cascade="all, delete-orphan")
    annotations: Mapped[list["Annotation"]] = relationship(back_populates="media", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_media_project_type", "project_id", "media_type"),
        Index("ix_media_project_status", "project_id", "indexing_status"),
    )


class MediaSource(Base):
    """External sources and references attached to media items."""
    __tablename__ = "media_sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    media_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("media.id", ondelete="CASCADE"), nullable=False, index=True)

    source_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'url', 'webpage', 'markdown', 'paper', 'api'
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)  # Scraped text, markdown content, etc.
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_extra: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    text_embedding_id: Mapped[str | None] = mapped_column(String(128), nullable=True)  # Qdrant point ID
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    media: Mapped["Media"] = relationship(back_populates="sources")


# Needed for relationship resolution
from app.models.project import Project  # noqa: E402
from app.models.dataset import DatasetItem, Annotation  # noqa: E402
