"""
Unit tests for the auth service (backend/app/services/auth.py).

Tests password hashing, JWT token creation/decoding, API key logic.
"""

import sys
import os
import uuid
import unittest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
import tests.mock_deps  # noqa: E402

from app.services import auth as auth_service
from tests.mock_deps import get_jose_jwt_mock, get_pwd_context_mock


class TestPasswordHashing(unittest.TestCase):
    """Tests for hash_password and verify_password."""

    def setUp(self):
        self.pwd_mock = get_pwd_context_mock()
        self.pwd_mock.reset_mock()

    def test_hash_password_calls_context(self):
        self.pwd_mock.hash.return_value = "$2b$12$hashedvalue"
        result = auth_service.hash_password("mypassword")
        self.pwd_mock.hash.assert_called_once_with("mypassword")
        self.assertEqual(result, "$2b$12$hashedvalue")

    def test_verify_password_correct(self):
        self.pwd_mock.verify.return_value = True
        result = auth_service.verify_password("plain", "hashed")
        self.pwd_mock.verify.assert_called_once_with("plain", "hashed")
        self.assertTrue(result)

    def test_verify_password_incorrect(self):
        self.pwd_mock.verify.return_value = False
        result = auth_service.verify_password("wrong", "hashed")
        self.assertFalse(result)


class TestAccessToken(unittest.TestCase):
    """Tests for JWT token creation and decoding."""

    def setUp(self):
        self.jwt_mock = get_jose_jwt_mock()
        self.jwt_mock.reset_mock()
        self.jwt_mock.encode.side_effect = None
        self.jwt_mock.decode.side_effect = None

    def test_create_access_token(self):
        user_id = uuid.uuid4()
        self.jwt_mock.encode.return_value = "encoded_token"

        result = auth_service.create_access_token(user_id)

        self.assertEqual(result, "encoded_token")
        self.jwt_mock.encode.assert_called_once()

        # Verify the payload structure
        call_args = self.jwt_mock.encode.call_args
        payload = call_args[0][0]
        self.assertEqual(payload["sub"], str(user_id))
        self.assertEqual(payload["type"], "access")
        self.assertIn("exp", payload)

    def test_create_access_token_expiry(self):
        user_id = uuid.uuid4()
        self.jwt_mock.encode.return_value = "token"

        auth_service.create_access_token(user_id)

        call_args = self.jwt_mock.encode.call_args
        payload = call_args[0][0]
        exp = payload["exp"]
        now = datetime.now(timezone.utc)
        # Expiry should be in the future
        self.assertGreater(exp, now)

    def test_decode_access_token_valid(self):
        user_id = uuid.uuid4()
        self.jwt_mock.decode.return_value = {
            "sub": str(user_id),
            "type": "access",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        }

        result = auth_service.decode_access_token("valid_token")

        self.assertEqual(result, user_id)
        self.jwt_mock.decode.assert_called_once()

    def test_decode_access_token_wrong_type(self):
        self.jwt_mock.decode.return_value = {
            "sub": str(uuid.uuid4()),
            "type": "refresh",  # Wrong type
        }

        result = auth_service.decode_access_token("wrong_type_token")
        self.assertIsNone(result)

    def test_decode_access_token_jwt_error(self):
        from jose import JWTError
        self.jwt_mock.decode.side_effect = JWTError("invalid")

        result = auth_service.decode_access_token("invalid_token")
        self.assertIsNone(result)

    def test_decode_access_token_value_error(self):
        self.jwt_mock.decode.return_value = {
            "sub": "not-a-uuid",
            "type": "access",
        }

        result = auth_service.decode_access_token("bad_sub_token")
        self.assertIsNone(result)


class TestAsyncAuthFunctions(unittest.IsolatedAsyncioTestCase):
    """Tests for async auth functions."""

    async def test_get_user_by_email(self):
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_user = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result

        result = await auth_service.get_user_by_email(mock_db, "test@test.com")

        self.assertEqual(result, mock_user)
        mock_db.execute.assert_called_once()

    async def test_get_user_by_email_not_found(self):
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        result = await auth_service.get_user_by_email(mock_db, "notfound@test.com")
        self.assertIsNone(result)

    async def test_get_user_by_id(self):
        mock_db = AsyncMock()
        user_id = uuid.uuid4()
        mock_user = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result

        result = await auth_service.get_user_by_id(mock_db, user_id)
        self.assertEqual(result, mock_user)

    async def test_authenticate_user_success(self):
        mock_db = AsyncMock()
        mock_user = MagicMock()
        mock_user.hashed_password = "hashed"
        mock_user.is_active = True

        pwd_mock = get_pwd_context_mock()
        pwd_mock.verify.return_value = True

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result

        result = await auth_service.authenticate_user(mock_db, "user@test.com", "password")
        self.assertEqual(result, mock_user)

    async def test_authenticate_user_wrong_password(self):
        mock_db = AsyncMock()
        mock_user = MagicMock()
        mock_user.hashed_password = "hashed"
        mock_user.is_active = True

        pwd_mock = get_pwd_context_mock()
        pwd_mock.verify.return_value = False

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result

        result = await auth_service.authenticate_user(mock_db, "user@test.com", "wrong")
        self.assertIsNone(result)

    async def test_authenticate_user_inactive(self):
        mock_db = AsyncMock()
        mock_user = MagicMock()
        mock_user.hashed_password = "hashed"
        mock_user.is_active = False

        pwd_mock = get_pwd_context_mock()
        pwd_mock.verify.return_value = True

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result

        result = await auth_service.authenticate_user(mock_db, "user@test.com", "password")
        self.assertIsNone(result)

    async def test_authenticate_user_not_found(self):
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        result = await auth_service.authenticate_user(mock_db, "notfound@test.com", "password")
        self.assertIsNone(result)

    async def test_create_user(self):
        mock_db = AsyncMock()
        pwd_mock = get_pwd_context_mock()
        pwd_mock.hash.return_value = "$2b$hashed"

        result = await auth_service.create_user(
            mock_db, email="new@test.com", password="password123", full_name="New User"
        )

        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()

    async def test_create_api_key(self):
        mock_db = AsyncMock()
        user_id = uuid.uuid4()

        api_key, raw_key = await auth_service.create_api_key(mock_db, user_id, "My Key")

        self.assertTrue(raw_key.startswith("if_"))
        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()

    async def test_create_api_key_with_expiry(self):
        mock_db = AsyncMock()
        user_id = uuid.uuid4()

        api_key, raw_key = await auth_service.create_api_key(mock_db, user_id, "Expiring Key", expires_in_days=30)

        self.assertTrue(raw_key.startswith("if_"))

    async def test_validate_api_key_valid(self):
        mock_db = AsyncMock()
        mock_api_key = MagicMock()
        mock_api_key.is_active = True
        mock_api_key.expires_at = None
        mock_api_key.user_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_api_key
        mock_db.execute.return_value = mock_result

        # Mock get_user_by_id
        mock_user = MagicMock()
        with patch.object(auth_service, 'get_user_by_id', new_callable=AsyncMock, return_value=mock_user):
            result = await auth_service.validate_api_key(mock_db, "if_testkey123")

        self.assertEqual(result, mock_user)

    async def test_validate_api_key_not_found(self):
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        result = await auth_service.validate_api_key(mock_db, "if_invalidkey")
        self.assertIsNone(result)

    async def test_validate_api_key_expired(self):
        mock_db = AsyncMock()
        mock_api_key = MagicMock()
        mock_api_key.is_active = True
        mock_api_key.expires_at = datetime.now(timezone.utc) - timedelta(days=1)  # expired

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_api_key
        mock_db.execute.return_value = mock_result

        result = await auth_service.validate_api_key(mock_db, "if_expiredkey")
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
