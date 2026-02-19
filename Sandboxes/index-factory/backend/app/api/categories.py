import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.category_assignment import CategoryAssignment
from app.services.auth import get_current_user
from pydantic import BaseModel

router = APIRouter(prefix="/api/categories", tags=["categories"])


class AssignmentCreate(BaseModel):
    reference_media_id: uuid.UUID | None = None
    document_id: uuid.UUID | None = None
    ontology_node_id: uuid.UUID
    confidence: float | None = None
    assigned_by: str = "manual"


class AssignmentResponse(BaseModel):
    id: uuid.UUID
    reference_media_id: uuid.UUID | None
    document_id: uuid.UUID | None
    ontology_node_id: uuid.UUID
    confidence: float | None
    is_confirmed: bool
    assigned_by: str

    model_config = {"from_attributes": True}


@router.get("/", response_model=list[AssignmentResponse])
async def list_assignments(
    ontology_node_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = select(CategoryAssignment)
    if ontology_node_id:
        q = q.where(CategoryAssignment.ontology_node_id == ontology_node_id)
    result = await db.execute(q.order_by(CategoryAssignment.created_at.desc()))
    return result.scalars().all()


@router.post("/", response_model=AssignmentResponse, status_code=201)
async def create_assignment(
    body: AssignmentCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    assignment = CategoryAssignment(
        reference_media_id=body.reference_media_id,
        document_id=body.document_id,
        ontology_node_id=body.ontology_node_id,
        confidence=body.confidence,
        assigned_by=body.assigned_by,
    )
    db.add(assignment)
    await db.flush()
    await db.refresh(assignment)
    return assignment


@router.patch("/{assignment_id}/confirm", response_model=AssignmentResponse)
async def confirm_assignment(
    assignment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(CategoryAssignment).where(CategoryAssignment.id == assignment_id))
    a = result.scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="Assignment not found")
    a.is_confirmed = True
    await db.flush()
    await db.refresh(a)
    return a


@router.delete("/{assignment_id}", status_code=204)
async def delete_assignment(
    assignment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(CategoryAssignment).where(CategoryAssignment.id == assignment_id))
    a = result.scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="Assignment not found")
    await db.delete(a)
