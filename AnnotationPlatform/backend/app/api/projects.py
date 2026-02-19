"""Project management endpoints."""

import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_admin, require_owner, require_viewer
from app.models.dataset import Dataset
from app.models.media import Media
from app.models.project import IndexingPrompt, Project, ProjectMember, ProjectRole
from app.models.user import User
from app.schemas.project import (
    IndexingPromptCreate, IndexingPromptOut,
    ProjectCreate, ProjectMemberAdd, ProjectMemberOut,
    ProjectOut, ProjectUpdate,
)
from app.services.auth import get_user_by_email

router = APIRouter(prefix="/projects", tags=["projects"])


def slugify(name: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", name.lower())
    return re.sub(r"[-\s]+", "-", slug).strip("-")


@router.post("", response_model=ProjectOut, status_code=201)
async def create_project(
    body: ProjectCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    slug = slugify(body.name)
    # Ensure slug uniqueness
    existing = await db.execute(select(Project).where(Project.slug == slug))
    if existing.scalar_one_or_none():
        slug = f"{slug}-{uuid.uuid4().hex[:6]}"

    project = Project(name=body.name, slug=slug, description=body.description, settings=body.settings)
    db.add(project)
    await db.flush()

    # Add creator as owner
    member = ProjectMember(project_id=project.id, user_id=user.id, role=ProjectRole.OWNER)
    db.add(member)
    await db.commit()

    return ProjectOut(
        **{c.name: getattr(project, c.name) for c in Project.__table__.columns},
        member_count=1, media_count=0, dataset_count=0,
    )


@router.get("", response_model=list[ProjectOut])
async def list_projects(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if user.is_superuser:
        query = select(Project)
    else:
        query = (
            select(Project)
            .join(ProjectMember, ProjectMember.project_id == Project.id)
            .where(ProjectMember.user_id == user.id)
        )

    result = await db.execute(query.order_by(Project.updated_at.desc()))
    projects = result.scalars().all()

    out = []
    for p in projects:
        # Get counts
        mc = await db.execute(select(func.count(Media.id)).where(Media.project_id == p.id))
        dc = await db.execute(select(func.count(Dataset.id)).where(Dataset.project_id == p.id))
        memc = await db.execute(select(func.count(ProjectMember.id)).where(ProjectMember.project_id == p.id))

        out.append(ProjectOut(
            **{c.name: getattr(p, c.name) for c in Project.__table__.columns},
            member_count=memc.scalar() or 0,
            media_count=mc.scalar() or 0,
            dataset_count=dc.scalar() or 0,
        ))
    return out


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    project_access: tuple = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
):
    project, _ = project_access
    mc = await db.execute(select(func.count(Media.id)).where(Media.project_id == project.id))
    dc = await db.execute(select(func.count(Dataset.id)).where(Dataset.project_id == project.id))
    memc = await db.execute(select(func.count(ProjectMember.id)).where(ProjectMember.project_id == project.id))

    return ProjectOut(
        **{c.name: getattr(project, c.name) for c in Project.__table__.columns},
        member_count=memc.scalar() or 0,
        media_count=mc.scalar() or 0,
        dataset_count=dc.scalar() or 0,
    )


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(
    body: ProjectUpdate,
    project_access: tuple = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    project, _ = project_access
    if body.name is not None:
        project.name = body.name
    if body.description is not None:
        project.description = body.description
    if body.settings is not None:
        project.settings = body.settings
    await db.commit()
    return await get_project(project_access=(project, ProjectRole.ADMIN), db=db)


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_access: tuple = Depends(require_owner),
    db: AsyncSession = Depends(get_db),
):
    project, _ = project_access
    await db.delete(project)
    await db.commit()


# ── Members ───────────────────────────────────────────────
@router.get("/{project_id}/members", response_model=list[ProjectMemberOut])
async def list_members(
    project_access: tuple = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
):
    project, _ = project_access
    result = await db.execute(
        select(ProjectMember, User.email, User.full_name)
        .join(User, User.id == ProjectMember.user_id)
        .where(ProjectMember.project_id == project.id)
        .order_by(ProjectMember.created_at)
    )
    rows = result.all()
    return [
        ProjectMemberOut(
            id=m.id, user_id=m.user_id, role=m.role, created_at=m.created_at,
            user_email=email, user_name=name,
        )
        for m, email, name in rows
    ]


@router.post("/{project_id}/members", response_model=ProjectMemberOut, status_code=201)
async def add_member(
    body: ProjectMemberAdd,
    project_access: tuple = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    project, _ = project_access
    target_user = await get_user_by_email(db, body.email)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check not already a member
    existing = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project.id,
            ProjectMember.user_id == target_user.id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="User is already a member")

    member = ProjectMember(project_id=project.id, user_id=target_user.id, role=body.role)
    db.add(member)
    await db.commit()

    return ProjectMemberOut(
        id=member.id, user_id=target_user.id, role=member.role,
        created_at=member.created_at, user_email=target_user.email,
        user_name=target_user.full_name,
    )


@router.delete("/{project_id}/members/{member_id}", status_code=204)
async def remove_member(
    member_id: uuid.UUID,
    project_access: tuple = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    project, _ = project_access
    result = await db.execute(
        select(ProjectMember).where(ProjectMember.id == member_id, ProjectMember.project_id == project.id)
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    if member.role == ProjectRole.OWNER:
        raise HTTPException(status_code=400, detail="Cannot remove the project owner")
    await db.delete(member)
    await db.commit()


# ── Indexing Prompts ──────────────────────────────────────
@router.get("/{project_id}/prompts", response_model=list[IndexingPromptOut])
async def list_prompts(
    project_access: tuple = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
):
    project, _ = project_access
    result = await db.execute(
        select(IndexingPrompt).where(IndexingPrompt.project_id == project.id).order_by(IndexingPrompt.created_at)
    )
    return [IndexingPromptOut.model_validate(p) for p in result.scalars().all()]


@router.post("/{project_id}/prompts", response_model=IndexingPromptOut, status_code=201)
async def create_prompt(
    body: IndexingPromptCreate,
    project_access: tuple = Depends(require_editor),
    db: AsyncSession = Depends(get_db),
):
    project, _ = project_access
    prompt = IndexingPrompt(project_id=project.id, **body.model_dump())
    db.add(prompt)
    await db.commit()
    return IndexingPromptOut.model_validate(prompt)
