"""FastAPI dependency injection."""

import uuid

from fastapi import Depends, HTTPException, Header, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.project import Project, ProjectMember, ProjectRole
from app.models.user import User
from app.services.auth import decode_access_token, get_user_by_id, validate_api_key

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    x_api_key: str | None = Header(None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Authenticate via Bearer JWT token or X-API-Key header."""
    # Try API key first
    if x_api_key:
        user = await validate_api_key(db, x_api_key)
        if user:
            return user

    # Try JWT
    if credentials:
        user_id = decode_access_token(credentials.credentials)
        if user_id:
            user = await get_user_by_id(db, user_id)
            if user and user.is_active:
                return user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_superuser(user: User = Depends(get_current_user)) -> User:
    if not user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superuser access required")
    return user


class ProjectAccess:
    """Dependency that validates project access and returns (project, role)."""

    def __init__(self, min_role: ProjectRole = ProjectRole.VIEWER):
        self.min_role = min_role
        self._role_hierarchy = {
            ProjectRole.OWNER: 0,
            ProjectRole.ADMIN: 1,
            ProjectRole.EDITOR: 2,
            ProjectRole.VIEWER: 3,
        }

    async def __call__(
        self,
        project_id: uuid.UUID,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> tuple[Project, ProjectRole]:
        # Superusers bypass project access checks
        if user.is_superuser:
            result = await db.execute(select(Project).where(Project.id == project_id))
            project = result.scalar_one_or_none()
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            return project, ProjectRole.OWNER

        # Check membership
        result = await db.execute(
            select(Project, ProjectMember.role)
            .join(ProjectMember, ProjectMember.project_id == Project.id)
            .where(Project.id == project_id, ProjectMember.user_id == user.id)
        )
        row = result.first()
        if not row:
            raise HTTPException(status_code=404, detail="Project not found")

        project, role = row
        if self._role_hierarchy[role] > self._role_hierarchy[self.min_role]:
            raise HTTPException(status_code=403, detail=f"Requires {self.min_role} role or higher")

        return project, role


# Pre-built access checkers
require_viewer = ProjectAccess(ProjectRole.VIEWER)
require_editor = ProjectAccess(ProjectRole.EDITOR)
require_admin = ProjectAccess(ProjectRole.ADMIN)
require_owner = ProjectAccess(ProjectRole.OWNER)
