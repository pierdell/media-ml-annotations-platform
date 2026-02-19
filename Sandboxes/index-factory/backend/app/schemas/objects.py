import re
from pydantic import BaseModel, field_validator
import uuid
from datetime import datetime

HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


class ObjectCreate(BaseModel):
    name: str
    description: str | None = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Name cannot be empty")
        if len(v) > 255:
            raise ValueError("Name must be at most 255 characters")
        return v


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

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Name cannot be empty")
        if len(v) > 255:
            raise ValueError("Name must be at most 255 characters")
        return v

    @field_validator("color")
    @classmethod
    def color_valid(cls, v: str | None) -> str | None:
        if v is not None and not HEX_COLOR_RE.match(v):
            raise ValueError("Color must be a valid hex color (e.g. #3b82f6)")
        return v


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
