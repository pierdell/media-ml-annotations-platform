"""
Integration tests for the Index Factory platform.

Tests end-to-end flows including:
- User registration and authentication flow
- Project CRUD with membership
- Media upload flow
- Dataset creation and management
- Search pipeline
- Indexing dispatch

These tests mock the database and external services but test
the full function call chains.
"""

import sys
import os
import uuid
import json
import hashlib
import unittest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
import tests.mock_deps  # noqa: E402

from app.services import auth as auth_service
from app.services.storage import compute_sha256, upload_media, get_thumbnail_url
from tests.mock_deps import get_jose_jwt_mock, get_pwd_context_mock, get_http_exception_class

HTTPException = get_http_exception_class()


class TestAuthenticationFlow(unittest.IsolatedAsyncioTestCase):
    """Integration test: Complete authentication flow."""

    async def test_register_login_flow(self):
        """Test: register a user, then login with credentials."""
        mock_db = AsyncMock()

        # 1. Register
        pwd_mock = get_pwd_context_mock()
        pwd_mock.hash.return_value = "$2b$12$hashed"

        user = await auth_service.create_user(
            mock_db, "alice@example.com", "strongpass123", "Alice"
        )
        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()

        # 2. Login - simulate finding the user
        mock_db.reset_mock()
        mock_user = MagicMock()
        mock_user.hashed_password = "$2b$12$hashed"
        mock_user.is_active = True
        mock_user.id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result

        pwd_mock.verify.return_value = True

        authenticated = await auth_service.authenticate_user(
            mock_db, "alice@example.com", "strongpass123"
        )
        self.assertIsNotNone(authenticated)

        # 3. Create access token
        jwt_mock = get_jose_jwt_mock()
        jwt_mock.encode.return_value = "jwt.token.here"

        token = auth_service.create_access_token(authenticated.id)
        self.assertEqual(token, "jwt.token.here")

        # 4. Decode token back
        jwt_mock.decode.return_value = {
            "sub": str(authenticated.id),
            "type": "access",
        }
        decoded_id = auth_service.decode_access_token(token)
        self.assertEqual(decoded_id, authenticated.id)


class TestApiKeyFlow(unittest.IsolatedAsyncioTestCase):
    """Integration test: API key creation and validation."""

    async def test_create_and_validate_api_key(self):
        mock_db = AsyncMock()
        user_id = uuid.uuid4()

        # 1. Create API key
        api_key, raw_key = await auth_service.create_api_key(
            mock_db, user_id, "CI Pipeline Key"
        )
        self.assertTrue(raw_key.startswith("if_"))
        self.assertGreater(len(raw_key), 20)

        # 2. Verify the key hash matches
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        # The key_hash should be stored in the DB record
        mock_db.add.assert_called_once()

        # 3. Validate the key
        mock_db.reset_mock()
        mock_api_key_record = MagicMock()
        mock_api_key_record.is_active = True
        mock_api_key_record.expires_at = None
        mock_api_key_record.user_id = user_id

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_api_key_record
        mock_db.execute.return_value = mock_result

        mock_user = MagicMock()
        with patch.object(auth_service, 'get_user_by_id', new_callable=AsyncMock, return_value=mock_user):
            validated_user = await auth_service.validate_api_key(mock_db, raw_key)

        self.assertEqual(validated_user, mock_user)


class TestMediaUploadFlow(unittest.TestCase):
    """Integration test: Media file upload and storage."""

    def setUp(self):
        import app.services.storage as storage_mod
        self.storage_mod = storage_mod
        self.mock_client = MagicMock()
        self.mock_client.bucket_exists.return_value = True
        storage_mod._client = self.mock_client

    def tearDown(self):
        self.storage_mod._client = None

    def test_upload_image_with_checksum(self):
        """Test: upload image data, compute checksum, get storage path."""
        project_id = uuid.uuid4()
        media_id = uuid.uuid4()
        image_data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100  # fake PNG

        # 1. Compute checksum
        checksum = compute_sha256(image_data)
        self.assertEqual(len(checksum), 64)

        # 2. Upload media
        storage_path = upload_media(
            project_id, media_id, "photo.png", image_data, "image/png"
        )
        self.assertEqual(storage_path, f"{project_id}/{media_id}.png")

        # 3. Verify put_object was called
        self.mock_client.put_object.assert_called_once()
        call_args = self.mock_client.put_object.call_args
        self.assertEqual(call_args[1]['length'], len(image_data))

    def test_upload_video_with_different_extension(self):
        project_id = uuid.uuid4()
        media_id = uuid.uuid4()

        path = upload_media(project_id, media_id, "clip.mp4", b"video_data", "video/mp4")
        self.assertTrue(path.endswith(".mp4"))

    def test_thumbnail_url_generation(self):
        url = get_thumbnail_url("proj1/media1_thumb.jpg")
        self.assertIn("proj1/media1_thumb.jpg", url)
        self.assertIn("thumbnails", url)


class TestSearchPipeline(unittest.TestCase):
    """Integration test: Search pipeline through Qdrant."""

    def setUp(self):
        import app.services.qdrant_service as qdrant_mod
        self.qdrant_mod = qdrant_mod
        self.mock_client = MagicMock()
        qdrant_mod._client = self.mock_client

    def tearDown(self):
        self.qdrant_mod._client = None

    def test_index_then_search(self):
        """Test: upsert an embedding, then search for similar ones."""
        project_id = str(uuid.uuid4())
        media_id = str(uuid.uuid4())

        # 1. Upsert embedding
        vector = [0.1] * 512
        self.qdrant_mod.upsert_embedding(
            collection="clip_embeddings",
            point_id=f"clip_{media_id}",
            vector=vector,
            payload={
                "media_id": media_id,
                "project_id": project_id,
                "media_type": "image",
            },
        )
        self.mock_client.upsert.assert_called_once()

        # 2. Search for similar
        mock_result = MagicMock()
        mock_result.id = f"clip_{media_id}"
        mock_result.score = 0.99
        mock_result.payload = {
            "media_id": media_id,
            "project_id": project_id,
            "media_type": "image",
        }
        self.mock_client.search.return_value = [mock_result]

        results = self.qdrant_mod.search_similar(
            collection="clip_embeddings",
            query_vector=[0.1] * 512,
            project_id=project_id,
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["media_id"], media_id)
        self.assertGreater(results[0]["score"], 0.9)

    def test_batch_upsert_then_delete(self):
        """Test: batch upsert, then delete by media ID."""
        media_id = str(uuid.uuid4())

        # 1. Batch upsert
        points = [
            (f"clip_{media_id}", [0.1] * 512, {"media_id": media_id}),
            (f"text_{media_id}", [0.2] * 384, {"media_id": media_id}),
        ]
        self.qdrant_mod.upsert_embeddings_batch("clip_embeddings", points)
        self.mock_client.upsert.assert_called_once()

        # 2. Delete
        self.qdrant_mod.delete_by_media_id(media_id)
        self.assertEqual(self.mock_client.delete.call_count, 3)  # 3 collections


class TestExportFormats(unittest.TestCase):
    """Integration test: Dataset export in multiple formats."""

    def setUp(self):
        from worker.tasks.indexing import (
            _export_coco, _export_yolo, _export_csv, _export_jsonl
        )
        self.export_coco = _export_coco
        self.export_yolo = _export_yolo
        self.export_csv = _export_csv
        self.export_jsonl = _export_jsonl

    def _make_sample_data(self):
        return {
            "dataset": "Test Dataset",
            "type": "object_detection",
            "version": "v1.0",
            "label_schema": {
                "labels": [
                    {"id": "person", "name": "Person"},
                    {"id": "car", "name": "Car"},
                ],
            },
            "items": [
                {
                    "media_id": "img001",
                    "split": "train",
                    "annotations": [
                        {
                            "type": "bbox",
                            "label": "person",
                            "confidence": 0.95,
                            "geometry": {"x": 10, "y": 20, "w": 100, "h": 200},
                            "attributes": {"occluded": False},
                            "frame_number": None,
                        },
                        {
                            "type": "bbox",
                            "label": "car",
                            "confidence": 0.87,
                            "geometry": {"x": 300, "y": 100, "w": 200, "h": 150},
                            "attributes": None,
                            "frame_number": None,
                        },
                    ],
                },
                {
                    "media_id": "img002",
                    "split": "val",
                    "annotations": [
                        {
                            "type": "polygon",
                            "label": "person",
                            "confidence": 0.92,
                            "geometry": {"points": [[10, 10], [50, 10], [50, 50], [10, 50]]},
                            "attributes": None,
                            "frame_number": None,
                        },
                    ],
                },
            ],
        }

    def test_all_formats_produce_valid_output(self):
        data = self._make_sample_data()

        # COCO
        coco_bytes = self.export_coco(data)
        coco = json.loads(coco_bytes)
        self.assertIn("images", coco)
        self.assertIn("annotations", coco)
        self.assertIn("categories", coco)
        self.assertEqual(len(coco["images"]), 2)
        self.assertEqual(len(coco["annotations"]), 3)

        # YOLO
        yolo_bytes = self.export_yolo(data)
        yolo_text = yolo_bytes.decode()
        lines = [l for l in yolo_text.split("\n") if l]
        self.assertEqual(len(lines), 2)  # Only bbox annotations

        # CSV
        csv_bytes = self.export_csv(data)
        csv_text = csv_bytes.decode()
        csv_lines = csv_text.strip().split("\n")
        self.assertEqual(len(csv_lines), 4)  # header + 3 annotations

        # JSONL
        jsonl_bytes = self.export_jsonl(data)
        jsonl_text = jsonl_bytes.decode()
        jsonl_lines = [l for l in jsonl_text.strip().split("\n") if l]
        self.assertEqual(len(jsonl_lines), 2)  # 2 items

    def test_coco_format_correctness(self):
        data = self._make_sample_data()
        coco = json.loads(self.export_coco(data))

        # Categories
        cat_names = [c["name"] for c in coco["categories"]]
        self.assertIn("Person", cat_names)
        self.assertIn("Car", cat_names)

        # Annotation bbox
        bbox_anns = [a for a in coco["annotations"] if "bbox" in a]
        self.assertEqual(len(bbox_anns), 2)
        self.assertEqual(bbox_anns[0]["bbox"], [10, 20, 100, 200])
        self.assertEqual(bbox_anns[0]["area"], 20000)

        # Annotation polygon
        poly_anns = [a for a in coco["annotations"] if "segmentation" in a]
        self.assertEqual(len(poly_anns), 1)
        self.assertEqual(poly_anns[0]["segmentation"], [[10, 10, 50, 10, 50, 50, 10, 50]])


class TestProjectAccessIntegration(unittest.IsolatedAsyncioTestCase):
    """Integration test: Project access control."""

    async def test_owner_can_access_admin_endpoint(self):
        from app.dependencies import ProjectAccess
        from app.models.project import ProjectRole

        access = ProjectAccess(min_role=ProjectRole.ADMIN)

        mock_user = MagicMock()
        mock_user.is_superuser = False
        mock_user.id = uuid.uuid4()

        mock_project = MagicMock()
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.first.return_value = (mock_project, ProjectRole.OWNER)
        mock_db.execute.return_value = mock_result

        project, role = await access(uuid.uuid4(), mock_user, mock_db)
        self.assertEqual(role, ProjectRole.OWNER)

    async def test_viewer_cannot_access_editor_endpoint(self):
        from app.dependencies import ProjectAccess
        from app.models.project import ProjectRole

        access = ProjectAccess(min_role=ProjectRole.EDITOR)

        mock_user = MagicMock()
        mock_user.is_superuser = False
        mock_user.id = uuid.uuid4()

        mock_project = MagicMock()
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.first.return_value = (mock_project, ProjectRole.VIEWER)
        mock_db.execute.return_value = mock_result

        with self.assertRaises(HTTPException) as cm:
            await access(uuid.uuid4(), mock_user, mock_db)
        self.assertEqual(cm.exception.status_code, 403)


class TestFullIndexingPipeline(unittest.TestCase):
    """Integration test: Full indexing pipeline from storage to vector DB."""

    def test_index_image_end_to_end(self):
        """Simulates: upload -> checksum -> store in MinIO -> CLIP encode -> upsert to Qdrant."""
        import app.services.storage as storage_mod
        import app.services.qdrant_service as qdrant_mod

        # Setup mocks
        mock_storage_client = MagicMock()
        mock_storage_client.bucket_exists.return_value = True
        storage_mod._client = mock_storage_client

        mock_qdrant_client = MagicMock()
        qdrant_mod._client = mock_qdrant_client

        project_id = uuid.uuid4()
        media_id = uuid.uuid4()
        image_data = b"fake_image_bytes"

        # Step 1: Compute checksum
        checksum = compute_sha256(image_data)
        self.assertEqual(len(checksum), 64)

        # Step 2: Upload to MinIO
        storage_path = storage_mod.upload_media(
            project_id, media_id, "test.jpg", image_data, "image/jpeg"
        )
        self.assertIn(str(project_id), storage_path)

        # Step 3: Generate CLIP embedding (mocked)
        fake_embedding = [0.1] * 512

        # Step 4: Upsert to Qdrant
        point_id = f"clip_{media_id}"
        qdrant_mod.upsert_embedding(
            collection="clip_embeddings",
            point_id=point_id,
            vector=fake_embedding,
            payload={
                "media_id": str(media_id),
                "project_id": str(project_id),
                "media_type": "image",
            },
        )
        mock_qdrant_client.upsert.assert_called_once()

        # Step 5: Search should work
        mock_result = MagicMock()
        mock_result.id = point_id
        mock_result.score = 0.99
        mock_result.payload = {"media_id": str(media_id)}
        mock_qdrant_client.search.return_value = [mock_result]

        results = qdrant_mod.search_similar("clip_embeddings", fake_embedding)
        self.assertEqual(len(results), 1)

        # Cleanup
        storage_mod._client = None
        qdrant_mod._client = None


if __name__ == '__main__':
    unittest.main()
