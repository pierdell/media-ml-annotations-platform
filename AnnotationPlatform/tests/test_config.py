"""
Unit tests for configuration (backend/app/config.py).

Tests settings defaults, computed properties, and singleton behavior.
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
import tests.mock_deps  # noqa: E402

from app.config import Settings, get_settings


class TestSettingsDefaults(unittest.TestCase):
    """Tests that Settings has correct default values."""

    def setUp(self):
        self.settings = get_settings()

    def test_default_environment(self):
        self.assertEqual(self.settings.ENVIRONMENT, "production")

    def test_default_secret_key(self):
        self.assertEqual(self.settings.SECRET_KEY, "CHANGE-ME")

    def test_default_algorithm(self):
        self.assertEqual(self.settings.ALGORITHM, "HS256")

    def test_default_token_expiry(self):
        self.assertEqual(self.settings.ACCESS_TOKEN_EXPIRE_MINUTES, 1440)

    def test_default_admin_email(self):
        self.assertEqual(self.settings.ADMIN_EMAIL, "admin@indexfactory.local")

    def test_default_database_url(self):
        self.assertIn("postgresql+asyncpg", self.settings.DATABASE_URL)

    def test_default_redis_url(self):
        self.assertIn("redis://", self.settings.REDIS_URL)

    def test_default_qdrant_settings(self):
        self.assertEqual(self.settings.QDRANT_HOST, "localhost")
        self.assertEqual(self.settings.QDRANT_PORT, 6334)

    def test_default_minio_settings(self):
        self.assertEqual(self.settings.MINIO_ENDPOINT, "localhost:9000")
        self.assertFalse(self.settings.MINIO_SECURE)

    def test_default_clip_model(self):
        self.assertEqual(self.settings.CLIP_MODEL_NAME, "ViT-B/32")

    def test_default_dino_model(self):
        self.assertEqual(self.settings.DINO_MODEL_NAME, "facebook/dinov2-base")

    def test_default_vlm_model(self):
        self.assertEqual(self.settings.VLM_MODEL_NAME, "Salesforce/blip2-opt-2.7b")

    def test_default_text_embedding_model(self):
        self.assertEqual(self.settings.TEXT_EMBEDDING_MODEL, "sentence-transformers/all-MiniLM-L6-v2")

    def test_max_upload_size(self):
        self.assertEqual(self.settings.MAX_UPLOAD_SIZE_MB, 2048)

    def test_allowed_image_types(self):
        self.assertIn("image/jpeg", self.settings.ALLOWED_IMAGE_TYPES)
        self.assertIn("image/png", self.settings.ALLOWED_IMAGE_TYPES)

    def test_allowed_video_types(self):
        self.assertIn("video/mp4", self.settings.ALLOWED_VIDEO_TYPES)

    def test_allowed_audio_types(self):
        self.assertIn("audio/mpeg", self.settings.ALLOWED_AUDIO_TYPES)


class TestSettingsSyncDatabaseUrl(unittest.TestCase):
    """Tests for the sync_database_url computed property."""

    def test_sync_url_removes_asyncpg(self):
        settings = get_settings()
        sync_url = settings.sync_database_url
        self.assertNotIn("+asyncpg", sync_url)
        self.assertIn("postgresql://", sync_url)

    def test_sync_url_preserves_rest_of_url(self):
        settings = get_settings()
        async_url = settings.DATABASE_URL
        sync_url = settings.sync_database_url
        # After removing +asyncpg, rest should be the same
        self.assertEqual(
            async_url.replace("+asyncpg", ""),
            sync_url,
        )


class TestSettingsSingleton(unittest.TestCase):
    """Tests that get_settings returns a cached instance."""

    def test_same_instance(self):
        s1 = get_settings()
        s2 = get_settings()
        self.assertIs(s1, s2)


class TestQdrantCollectionNames(unittest.TestCase):
    """Tests for Qdrant collection name settings."""

    def test_collection_names(self):
        settings = get_settings()
        self.assertEqual(settings.QDRANT_COLLECTION_CLIP, "clip_embeddings")
        self.assertEqual(settings.QDRANT_COLLECTION_DINO, "dino_embeddings")
        self.assertEqual(settings.QDRANT_COLLECTION_TEXT, "text_embeddings")


class TestMinioBucketNames(unittest.TestCase):
    """Tests for MinIO bucket name settings."""

    def test_bucket_names(self):
        settings = get_settings()
        self.assertEqual(settings.MINIO_MEDIA_BUCKET, "media")
        self.assertEqual(settings.MINIO_THUMBNAIL_BUCKET, "thumbnails")
        self.assertEqual(settings.MINIO_EXPORT_BUCKET, "exports")


if __name__ == '__main__':
    unittest.main()
