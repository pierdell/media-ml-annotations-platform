from pydantic import BaseModel
import uuid
from datetime import datetime


class ObjectCreate(BaseModel):
    name: str
    description: str | None = None


class ObjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class ObjectResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OntologyNodeCreate(BaseModel):
    name: str
    parent_id: uuid.UUID | None = None
    description: str | None = None
    color: str | None = None
    sort_order: int = 0


class OntologyNodeUpdate(BaseModel):
    name: str | None = None
    parent_id: uuid.UUID | None = None
    description: str | None = None
    color: str | None = None
    sort_order: int | None = None


class OntologyNodeResponse(BaseModel):
    id: uuid.UUID
    object_id: uuid.UUID
    parent_id: uuid.UUID | None
    name: str
    description: str | None
    color: str | None
    sort_order: int
    created_at: datetime
    children: list["OntologyNodeResponse"] = []

    model_config = {"from_attributes": True}
