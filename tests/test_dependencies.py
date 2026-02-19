"""
Unit tests for FastAPI dependencies (backend/app/dependencies.py).

Tests authentication middleware and project access control.
"""

import sys
import os
import uuid
import unittest
from unittest.mock import MagicMock, AsyncMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
import tests.mock_deps  # noqa: E402

from app.dependencies import ProjectAccess, get_current_user, get_current_superuser
from app.models.project import ProjectRole
from tests.mock_deps import get_http_exception_class

HTTPException = get_http_exception_class()


class TestProjectAccess(unittest.TestCase):
    """Tests for the ProjectAccess dependency class."""

    def test_role_hierarchy(self):
        access = ProjectAccess(min_role=ProjectRole.VIEWER)
        # OWNER < ADMIN < EDITOR < VIEWER (lower number = higher privilege)
        self.assertLess(access._role_hierarchy[ProjectRole.OWNER], access._role_hierarchy[ProjectRole.ADMIN])
        self.assertLess(access._role_hierarchy[ProjectRole.ADMIN], access._role_hierarchy[ProjectRole.EDITOR])
        self.assertLess(access._role_hierarchy[ProjectRole.EDITOR], access._role_hierarchy[ProjectRole.VIEWER])

    def test_min_role_stored(self):
        access = ProjectAccess(min_role=ProjectRole.EDITOR)
        self.assertEqual(access.min_role, ProjectRole.EDITOR)

    def test_default_min_role(self):
        access = ProjectAccess()
        self.assertEqual(access.min_role, ProjectRole.VIEWER)


class TestProjectAccessCall(unittest.IsolatedAsyncioTestCase):
    """Tests for ProjectAccess.__call__ method."""

    async def test_superuser_bypasses_access_check(self):
        access = ProjectAccess(min_role=ProjectRole.ADMIN)
        project_id = uuid.uuid4()

        mock_user = MagicMock()
        mock_user.is_superuser = True

        mock_project = MagicMock()
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_project
        mock_db.execute.return_value = mock_result

        project, role = await access(project_id, mock_user, mock_db)
        self.assertEqual(project, mock_project)
        self.assertEqual(role, ProjectRole.OWNER)

    async def test_superuser_project_not_found(self):
        access = ProjectAccess(min_role=ProjectRole.VIEWER)
        project_id = uuid.uuid4()

        mock_user = MagicMock()
        mock_user.is_superuser = True

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with self.assertRaises(HTTPException) as cm:
            await access(project_id, mock_user, mock_db)
        self.assertEqual(cm.exception.status_code, 404)

    async def test_member_with_sufficient_role(self):
        access = ProjectAccess(min_role=ProjectRole.EDITOR)
        project_id = uuid.uuid4()

        mock_user = MagicMock()
        mock_user.is_superuser = False
        mock_user.id = uuid.uuid4()

        mock_project = MagicMock()
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.first.return_value = (mock_project, ProjectRole.EDITOR)
        mock_db.execute.return_value = mock_result

        project, role = await access(project_id, mock_user, mock_db)
        self.assertEqual(project, mock_project)
        self.assertEqual(role, ProjectRole.EDITOR)

    async def test_member_with_higher_role(self):
        access = ProjectAccess(min_role=ProjectRole.EDITOR)
        project_id = uuid.uuid4()

        mock_user = MagicMock()
        mock_user.is_superuser = False
        mock_user.id = uuid.uuid4()

        mock_project = MagicMock()
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.first.return_value = (mock_project, ProjectRole.ADMIN)
        mock_db.execute.return_value = mock_result

        project, role = await access(project_id, mock_user, mock_db)
        self.assertEqual(project, mock_project)
        self.assertEqual(role, ProjectRole.ADMIN)

    async def test_member_with_insufficient_role(self):
        access = ProjectAccess(min_role=ProjectRole.ADMIN)
        project_id = uuid.uuid4()

        mock_user = MagicMock()
        mock_user.is_superuser = False
        mock_user.id = uuid.uuid4()

        mock_project = MagicMock()
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.first.return_value = (mock_project, ProjectRole.VIEWER)
        mock_db.execute.return_value = mock_result

        with self.assertRaises(HTTPException) as cm:
            await access(project_id, mock_user, mock_db)
        self.assertEqual(cm.exception.status_code, 403)

    async def test_non_member_gets_404(self):
        access = ProjectAccess(min_role=ProjectRole.VIEWER)
        project_id = uuid.uuid4()

        mock_user = MagicMock()
        mock_user.is_superuser = False
        mock_user.id = uuid.uuid4()

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_db.execute.return_value = mock_result

        with self.assertRaises(HTTPException) as cm:
            await access(project_id, mock_user, mock_db)
        self.assertEqual(cm.exception.status_code, 404)


class TestGetCurrentUser(unittest.IsolatedAsyncioTestCase):
    """Tests for the get_current_user dependency."""

    async def test_api_key_auth(self):
        mock_db = AsyncMock()
        mock_user = MagicMock()

        with patch('app.dependencies.validate_api_key', new_callable=AsyncMock, return_value=mock_user):
            result = await get_current_user(
                credentials=None,
                x_api_key="if_testkey123",
                db=mock_db,
            )
        self.assertEqual(result, mock_user)

    async def test_jwt_auth(self):
        mock_db = AsyncMock()
        mock_user = MagicMock()
        mock_user.is_active = True
        user_id = uuid.uuid4()

        mock_creds = MagicMock()
        mock_creds.credentials = "valid_jwt_token"

        with patch('app.dependencies.decode_access_token', return_value=user_id), \
             patch('app.dependencies.get_user_by_id', new_callable=AsyncMock, return_value=mock_user):
            result = await get_current_user(
                credentials=mock_creds,
                x_api_key=None,
                db=mock_db,
            )
        self.assertEqual(result, mock_user)

    async def test_no_credentials_raises_401(self):
        mock_db = AsyncMock()

        with self.assertRaises(HTTPException) as cm:
            await get_current_user(credentials=None, x_api_key=None, db=mock_db)
        self.assertEqual(cm.exception.status_code, 401)

    async def test_invalid_jwt_raises_401(self):
        mock_db = AsyncMock()
        mock_creds = MagicMock()
        mock_creds.credentials = "invalid_token"

        with patch('app.dependencies.decode_access_token', return_value=None):
            with self.assertRaises(HTTPException) as cm:
                await get_current_user(credentials=mock_creds, x_api_key=None, db=mock_db)
            self.assertEqual(cm.exception.status_code, 401)

    async def test_inactive_user_raises_401(self):
        mock_db = AsyncMock()
        mock_user = MagicMock()
        mock_user.is_active = False
        user_id = uuid.uuid4()

        mock_creds = MagicMock()
        mock_creds.credentials = "valid_token"

        with patch('app.dependencies.decode_access_token', return_value=user_id), \
             patch('app.dependencies.get_user_by_id', new_callable=AsyncMock, return_value=mock_user):
            with self.assertRaises(HTTPException) as cm:
                await get_current_user(credentials=mock_creds, x_api_key=None, db=mock_db)
            self.assertEqual(cm.exception.status_code, 401)


class TestGetCurrentSuperuser(unittest.IsolatedAsyncioTestCase):
    """Tests for the get_current_superuser dependency."""

    async def test_superuser_passes(self):
        mock_user = MagicMock()
        mock_user.is_superuser = True

        result = await get_current_superuser(mock_user)
        self.assertEqual(result, mock_user)

    async def test_non_superuser_raises_403(self):
        mock_user = MagicMock()
        mock_user.is_superuser = False

        with self.assertRaises(HTTPException) as cm:
            await get_current_superuser(mock_user)
        self.assertEqual(cm.exception.status_code, 403)


class TestProjectRoleEnum(unittest.TestCase):
    """Tests for ProjectRole enum values."""

    def test_role_values(self):
        self.assertEqual(ProjectRole.OWNER, "owner")
        self.assertEqual(ProjectRole.ADMIN, "admin")
        self.assertEqual(ProjectRole.EDITOR, "editor")
        self.assertEqual(ProjectRole.VIEWER, "viewer")

    def test_role_count(self):
        self.assertEqual(len(ProjectRole), 4)


if __name__ == '__main__':
    unittest.main()
