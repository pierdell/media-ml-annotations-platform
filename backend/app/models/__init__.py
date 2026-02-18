"""SQLAlchemy models - import all for Alembic auto-detection."""

from app.database import Base
from app.models.user import User, ApiKey
from app.models.project import Project, ProjectMember, ProjectRole, IndexingPrompt
from app.models.media import Media, MediaSource, MediaType, IndexingStatus
from app.models.dataset import (
    Dataset, DatasetItem, DatasetVersion,
    Annotation, DatasetType, DatasetStatus, AnnotationType,
)

__all__ = [
    "Base",
    "User", "ApiKey",
    "Project", "ProjectMember", "ProjectRole", "IndexingPrompt",
    "Media", "MediaSource", "MediaType", "IndexingStatus",
    "Dataset", "DatasetItem", "DatasetVersion",
    "Annotation", "DatasetType", "DatasetStatus", "AnnotationType",
]
