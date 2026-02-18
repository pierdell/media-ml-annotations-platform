"""
Unit tests for the storage service (backend/app/services/storage.py).

Tests MinIO storage operations with mocked MinIO client.
"""

import sys
import os
import uuid
import unittest
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
import tests.mock_deps  # noqa: E402

from app.services import storage as storage_mod


class TestStorageClient(unittest.TestCase):
    """Tests for get_storage_client singleton."""

    def setUp(self):
        # Reset singleton
        storage_mod._client = None

    def test_get_storage_client_creates_instance(self):
        with patch.object(storage_mod, 'Minio') as mock_minio:
            mock_minio.return_value = MagicMock()
            client = storage_mod.get_storage_client()
            mock_minio.assert_called_once()
            self.assertIsNotNone(client)

    def test_get_storage_client_returns_same_instance(self):
        with patch.object(storage_mod, 'Minio') as mock_minio:
            mock_instance = MagicMock()
            mock_minio.return_value = mock_instance
            client1 = storage_mod.get_storage_client()
            client2 = storage_mod.get_storage_client()
            self.assertIs(client1, client2)
            mock_minio.assert_called_once()  # Only created once


class TestUploadMedia(unittest.TestCase):
    """Tests for upload_media function."""

    def setUp(self):
        self.mock_client = MagicMock()
        self.mock_client.bucket_exists.return_value = True
        storage_mod._client = self.mock_client

    def tearDown(self):
        storage_mod._client = None

    def test_upload_media_returns_correct_path(self):
        project_id = uuid.uuid4()
        media_id = uuid.uuid4()

        result = storage_mod.upload_media(
            project_id=project_id,
            media_id=media_id,
            filename="photo.jpg",
            data=b"fake image data",
            content_type="image/jpeg",
        )

        expected_path = f"{project_id}/{media_id}.jpg"
        self.assertEqual(result, expected_path)

    def test_upload_media_calls_put_object(self):
        project_id = uuid.uuid4()
        media_id = uuid.uuid4()

        storage_mod.upload_media(
            project_id=project_id,
            media_id=media_id,
            filename="video.mp4",
            data=b"fake video data",
            content_type="video/mp4",
        )

        self.mock_client.put_object.assert_called_once()
        call_args = self.mock_client.put_object.call_args
        self.assertEqual(call_args[0][0], storage_mod.settings.MINIO_MEDIA_BUCKET)
        self.assertEqual(call_args[1]['content_type'], "video/mp4")
        self.assertEqual(call_args[1]['length'], len(b"fake video data"))

    def test_upload_media_creates_bucket_if_missing(self):
        self.mock_client.bucket_exists.return_value = False
        project_id = uuid.uuid4()
        media_id = uuid.uuid4()

        storage_mod.upload_media(project_id, media_id, "test.png", b"data", "image/png")

        self.mock_client.make_bucket.assert_called_once()

    def test_upload_preserves_file_extension(self):
        project_id = uuid.uuid4()
        media_id = uuid.uuid4()

        result = storage_mod.upload_media(project_id, media_id, "document.pdf", b"data", "application/pdf")
        self.assertTrue(result.endswith(".pdf"))

        result2 = storage_mod.upload_media(project_id, media_id, "image.webp", b"data", "image/webp")
        self.assertTrue(result2.endswith(".webp"))


class TestUploadThumbnail(unittest.TestCase):
    """Tests for upload_thumbnail function."""

    def setUp(self):
        self.mock_client = MagicMock()
        self.mock_client.bucket_exists.return_value = True
        storage_mod._client = self.mock_client

    def tearDown(self):
        storage_mod._client = None

    def test_upload_thumbnail_path_format(self):
        project_id = uuid.uuid4()
        media_id = uuid.uuid4()

        result = storage_mod.upload_thumbnail(project_id, media_id, b"thumb_data")

        expected = f"{project_id}/{media_id}_thumb.jpg"
        self.assertEqual(result, expected)

    def test_upload_thumbnail_default_content_type(self):
        project_id = uuid.uuid4()
        media_id = uuid.uuid4()

        storage_mod.upload_thumbnail(project_id, media_id, b"thumb_data")

        call_args = self.mock_client.put_object.call_args
        self.assertEqual(call_args[1]['content_type'], "image/jpeg")


class TestGetThumbnailUrl(unittest.TestCase):
    """Tests for get_thumbnail_url function."""

    def test_http_url(self):
        # Settings default MINIO_SECURE is False
        result = storage_mod.get_thumbnail_url("project1/media1_thumb.jpg")
        self.assertTrue(result.startswith("http://"))
        self.assertIn("project1/media1_thumb.jpg", result)
        self.assertIn(storage_mod.settings.MINIO_THUMBNAIL_BUCKET, result)


class TestDownloadMedia(unittest.TestCase):
    """Tests for download_media function."""

    def setUp(self):
        self.mock_client = MagicMock()
        storage_mod._client = self.mock_client

    def tearDown(self):
        storage_mod._client = None

    def test_download_media_returns_bytes(self):
        mock_response = MagicMock()
        mock_response.read.return_value = b"file content"
        self.mock_client.get_object.return_value = mock_response

        result = storage_mod.download_media("project/media.jpg")

        self.assertEqual(result, b"file content")
        mock_response.close.assert_called_once()
        mock_response.release_conn.assert_called_once()


class TestDeleteMedia(unittest.TestCase):
    """Tests for delete_media function."""

    def setUp(self):
        self.mock_client = MagicMock()
        storage_mod._client = self.mock_client

    def tearDown(self):
        storage_mod._client = None

    def test_delete_media_calls_remove(self):
        storage_mod.delete_media("project/media.jpg")
        self.mock_client.remove_object.assert_called_once_with(
            storage_mod.settings.MINIO_MEDIA_BUCKET, "project/media.jpg"
        )

    def test_delete_media_ignores_s3_error(self):
        from minio.error import S3Error
        self.mock_client.remove_object.side_effect = S3Error("not found")
        # Should not raise
        storage_mod.delete_media("project/nonexistent.jpg")


class TestDeleteThumbnail(unittest.TestCase):
    """Tests for delete_thumbnail function."""

    def setUp(self):
        self.mock_client = MagicMock()
        storage_mod._client = self.mock_client

    def tearDown(self):
        storage_mod._client = None

    def test_delete_thumbnail_calls_remove(self):
        storage_mod.delete_thumbnail("project/media_thumb.jpg")
        self.mock_client.remove_object.assert_called_once_with(
            storage_mod.settings.MINIO_THUMBNAIL_BUCKET, "project/media_thumb.jpg"
        )


class TestUploadExport(unittest.TestCase):
    """Tests for upload_export function."""

    def setUp(self):
        self.mock_client = MagicMock()
        self.mock_client.bucket_exists.return_value = True
        storage_mod._client = self.mock_client

    def tearDown(self):
        storage_mod._client = None

    def test_export_coco_extension(self):
        result = storage_mod.upload_export(
            uuid.uuid4(), uuid.uuid4(), "v1.0", b"coco data", "coco"
        )
        self.assertTrue(result.endswith(".json"))

    def test_export_yolo_extension(self):
        result = storage_mod.upload_export(
            uuid.uuid4(), uuid.uuid4(), "v1.0", b"yolo data", "yolo"
        )
        self.assertTrue(result.endswith(".zip"))

    def test_export_csv_extension(self):
        result = storage_mod.upload_export(
            uuid.uuid4(), uuid.uuid4(), "v1.0", b"csv data", "csv"
        )
        self.assertTrue(result.endswith(".csv"))

    def test_export_jsonl_extension(self):
        result = storage_mod.upload_export(
            uuid.uuid4(), uuid.uuid4(), "v1.0", b"jsonl data", "jsonl"
        )
        self.assertTrue(result.endswith(".jsonl"))

    def test_export_unknown_format_defaults_to_zip(self):
        result = storage_mod.upload_export(
            uuid.uuid4(), uuid.uuid4(), "v1.0", b"data", "unknown"
        )
        self.assertTrue(result.endswith(".zip"))

    def test_export_path_includes_version_tag(self):
        pid = uuid.uuid4()
        did = uuid.uuid4()
        result = storage_mod.upload_export(pid, did, "v2.1", b"data", "coco")
        self.assertIn("v2.1", result)
        self.assertIn(str(pid), result)
        self.assertIn(str(did), result)


if __name__ == '__main__':
    unittest.main()
