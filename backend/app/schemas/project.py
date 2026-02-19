"""Project schemas."""

import uuid
from datetime import datetime
from pydantic import BaseModel, Field

from app.models.project import ProjectRole


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    settings: dict = Field(default_factory=dict)


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    settings: dict | None = None


class ProjectOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    description: str | None
    settings: dict
    created_at: datetime
    updated_at: datetime
    member_count: int = 0
    media_count: int = 0
    dataset_count: int = 0

    model_config = {"from_attributes": True}


class ProjectMemberAdd(BaseModel):
    email: str
    role: ProjectRole = ProjectRole.EDITOR


class ProjectMemberOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    user_email: str = ""
    user_name: str = ""
    role: ProjectRole
    created_at: datetime

    model_config = {"from_attributes": True}


class IndexingPromptCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    prompt_template: str = Field(min_length=1)
    model_name: str | None = None
    is_default: bool = False


class IndexingPromptOut(BaseModel):
    id: uuid.UUID
    name: str
    prompt_template: str
    model_name: str | None
    is_default: bool
    created_at: datetime

    model_config = {"from_attributes": True}
