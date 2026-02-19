"""SQLAlchemy models - import all for Alembic auto-detection."""

from app.database import Base
from app.models.user import User, ApiKey
from app.models.project import Project, ProjectMember, ProjectRole, IndexingPrompt
from app.models.media import Media, MediaSource, MediaType, IndexingStatus
from app.models.dataset import (
    Dataset, DatasetItem, DatasetVersion,
    Annotation, DatasetType, DatasetStatus, AnnotationType,
)
from app.models.quality import AnnotationReview, AgreementScore, ReviewStatus
from app.models.training import TrainingJob, TrainingStatus

# Conditionally import billing models
try:
    from app.config import get_settings
    if get_settings().BILLING_ENABLED:
        from app.billing.models import UsageRecord, ProjectQuota, Subscription
except Exception:
    pass

__all__ = [
    "Base",
    "User", "ApiKey",
    "Project", "ProjectMember", "ProjectRole", "IndexingPrompt",
    "Media", "MediaSource", "MediaType", "IndexingStatus",
    "Dataset", "DatasetItem", "DatasetVersion",
    "Annotation", "DatasetType", "DatasetStatus", "AnnotationType",
    "AnnotationReview", "AgreementScore", "ReviewStatus",
    "TrainingJob", "TrainingStatus",
]
