import uuid
from datetime import datetime
from sqlalchemy import String, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class CategoryAssignment(Base):
    __tablename__ = "category_assignments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    reference_media_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("reference_media.id", ondelete="CASCADE"))
    document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    ontology_node_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ontology_nodes.id", ondelete="CASCADE"), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float)
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    assigned_by: Mapped[str] = mapped_column(String(50), default="auto")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    reference_media = relationship("ReferenceMedia", back_populates="assignments")
    document = relationship("Document", back_populates="assignments")
    ontology_node = relationship("OntologyNode", back_populates="assignments")
