"""Model training job models."""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    DateTime, Enum, Float, ForeignKey,
    Index, Integer, String, Text, func,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TrainingStatus(StrEnum):
    QUEUED = "queued"
    PREPARING = "preparing"
    TRAINING = "training"
    EVALUATING = "evaluating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TrainingJob(Base):
    """A model training or fine-tuning job."""
    __tablename__ = "training_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    dataset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("datasets.id", ondelete="SET NULL"), nullable=True)
    dataset_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("dataset_versions.id", ondelete="SET NULL"), nullable=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    model_type: Mapped[str] = mapped_column(String(100), nullable=False)
    # e.g. 'image_classifier', 'object_detector', 'clip_finetune', 'custom'

    base_model: Mapped[str] = mapped_column(String(255), nullable=False)
    # e.g. 'resnet50', 'yolov8n', 'ViT-B/32', 'custom_model_path'

    status: Mapped[TrainingStatus] = mapped_column(
        Enum(TrainingStatus, native_enum=False), default=TrainingStatus.QUEUED
    )

    # Hyperparameters
    hyperparameters: Mapped[dict] = mapped_column(JSONB, default=dict)
    # e.g. {"epochs": 50, "batch_size": 32, "learning_rate": 0.001, "optimizer": "adam"}

    # Training progress
    current_epoch: Mapped[int] = mapped_column(Integer, default=0)
    total_epochs: Mapped[int] = mapped_column(Integer, default=0)
    train_loss: Mapped[float | None] = mapped_column(Float, nullable=True)
    val_loss: Mapped[float | None] = mapped_column(Float, nullable=True)
    metrics: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # e.g. {"accuracy": 0.95, "f1": 0.93, "mAP": 0.87, "loss_history": [...]}

    # Output
    model_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    export_format: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # e.g. 'pytorch', 'onnx', 'tensorrt', 'torchscript'

    # Error info
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_training_project_status", "project_id", "status"),
    )
