import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.user import User
from app.models.object import Object
from app.models.ontology import OntologyNode
from app.schemas.objects import (
    ObjectCreate, ObjectUpdate, ObjectResponse,
    OntologyNodeCreate, OntologyNodeUpdate, OntologyNodeResponse,
)
from app.services.auth import get_current_user

router = APIRouter(prefix="/api/objects", tags=["objects"])


# ── Objects CRUD ─────────────────────────────────────────────────
@router.get("/", response_model=list[ObjectResponse])
async def list_objects(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Object).where(Object.user_id == user.id).order_by(Object.created_at.desc()))
    return result.scalars().all()


@router.post("/", response_model=ObjectResponse, status_code=201)
async def create_object(body: ObjectCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    obj = Object(user_id=user.id, name=body.name, description=body.description)
    db.add(obj)
    await db.flush()
    await db.refresh(obj)
    return obj


@router.get("/{object_id}", response_model=ObjectResponse)
async def get_object(object_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Object).where(Object.id == object_id, Object.user_id == user.id))
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Object not found")
    return obj


@router.patch("/{object_id}", response_model=ObjectResponse)
async def update_object(object_id: uuid.UUID, body: ObjectUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Object).where(Object.id == object_id, Object.user_id == user.id))
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Object not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    await db.flush()
    await db.refresh(obj)
    return obj


@router.delete("/{object_id}", status_code=204)
async def delete_object(object_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Object).where(Object.id == object_id, Object.user_id == user.id))
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Object not found")
    await db.delete(obj)


# ── Ontology CRUD ────────────────────────────────────────────────
@router.get("/{object_id}/ontology", response_model=list[OntologyNodeResponse])
async def list_ontology(object_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    # Verify ownership
    obj_result = await db.execute(select(Object).where(Object.id == object_id, Object.user_id == user.id))
    if not obj_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Object not found")
    result = await db.execute(
        select(OntologyNode)
        .where(OntologyNode.object_id == object_id, OntologyNode.parent_id.is_(None))
        .options(selectinload(OntologyNode.children))
        .order_by(OntologyNode.sort_order)
    )
    return result.scalars().all()


@router.post("/{object_id}/ontology", response_model=OntologyNodeResponse, status_code=201)
async def create_ontology_node(object_id: uuid.UUID, body: OntologyNodeCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    obj_result = await db.execute(select(Object).where(Object.id == object_id, Object.user_id == user.id))
    if not obj_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Object not found")
    node = OntologyNode(
        object_id=object_id,
        parent_id=body.parent_id,
        name=body.name,
        description=body.description,
        color=body.color,
        sort_order=body.sort_order,
    )
    db.add(node)
    await db.flush()
    await db.refresh(node)
    return node


@router.patch("/{object_id}/ontology/{node_id}", response_model=OntologyNodeResponse)
async def update_ontology_node(object_id: uuid.UUID, node_id: uuid.UUID, body: OntologyNodeUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(OntologyNode).where(OntologyNode.id == node_id, OntologyNode.object_id == object_id))
    node = result.scalar_one_or_none()
    if not node:
        raise HTTPException(status_code=404, detail="Ontology node not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(node, field, value)
    await db.flush()
    await db.refresh(node)
    return node


@router.delete("/{object_id}/ontology/{node_id}", status_code=204)
async def delete_ontology_node(object_id: uuid.UUID, node_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(OntologyNode).where(OntologyNode.id == node_id, OntologyNode.object_id == object_id))
    node = result.scalar_one_or_none()
    if not node:
        raise HTTPException(status_code=404, detail="Ontology node not found")
    await db.delete(node)
