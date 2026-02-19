"""
Unit tests for the Qdrant service (backend/app/services/qdrant_service.py).

Tests vector operations with mocked Qdrant client.
"""

import sys
import os
import uuid
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
import tests.mock_deps  # noqa: E402

from app.services import qdrant_service as qdrant_mod


class TestConstants(unittest.TestCase):
    """Test embedding dimension constants."""

    def test_clip_dim(self):
        self.assertEqual(qdrant_mod.CLIP_DIM, 512)

    def test_dino_dim(self):
        self.assertEqual(qdrant_mod.DINO_DIM, 768)

    def test_text_dim(self):
        self.assertEqual(qdrant_mod.TEXT_DIM, 384)


class TestGetQdrantClient(unittest.TestCase):
    """Tests for client singleton."""

    def setUp(self):
        qdrant_mod._client = None

    def test_creates_client(self):
        with patch.object(qdrant_mod, 'QdrantClient') as mock_cls:
            mock_cls.return_value = MagicMock()
            client = qdrant_mod.get_qdrant_client()
            mock_cls.assert_called_once()
            self.assertIsNotNone(client)

    def test_returns_same_client(self):
        with patch.object(qdrant_mod, 'QdrantClient') as mock_cls:
            mock_cls.return_value = MagicMock()
            c1 = qdrant_mod.get_qdrant_client()
            c2 = qdrant_mod.get_qdrant_client()
            self.assertIs(c1, c2)

    def tearDown(self):
        qdrant_mod._client = None


class TestUpsertEmbedding(unittest.TestCase):
    """Tests for upsert_embedding function."""

    def setUp(self):
        self.mock_client = MagicMock()
        qdrant_mod._client = self.mock_client

    def tearDown(self):
        qdrant_mod._client = None

    def test_upsert_single_embedding(self):
        vector = [0.1] * 512
        payload = {"media_id": "m1", "project_id": "p1", "media_type": "image"}

        qdrant_mod.upsert_embedding("clip_embeddings", "point1", vector, payload)

        self.mock_client.upsert.assert_called_once()
        call_args = self.mock_client.upsert.call_args
        self.assertEqual(call_args[1]['collection_name'], "clip_embeddings")


class TestUpsertEmbeddingsBatch(unittest.TestCase):
    """Tests for batch upsert."""

    def setUp(self):
        self.mock_client = MagicMock()
        qdrant_mod._client = self.mock_client

    def tearDown(self):
        qdrant_mod._client = None

    def test_upsert_batch(self):
        points = [
            ("p1", [0.1] * 512, {"media_id": "m1"}),
            ("p2", [0.2] * 512, {"media_id": "m2"}),
            ("p3", [0.3] * 512, {"media_id": "m3"}),
        ]

        qdrant_mod.upsert_embeddings_batch("clip_embeddings", points)

        self.mock_client.upsert.assert_called_once()

    def test_upsert_empty_batch(self):
        qdrant_mod.upsert_embeddings_batch("clip_embeddings", [])
        self.mock_client.upsert.assert_called_once()


class TestSearchSimilar(unittest.TestCase):
    """Tests for search_similar function."""

    def setUp(self):
        self.mock_client = MagicMock()
        qdrant_mod._client = self.mock_client

    def tearDown(self):
        qdrant_mod._client = None

    def test_search_basic(self):
        mock_result_1 = MagicMock()
        mock_result_1.id = "point1"
        mock_result_1.score = 0.95
        mock_result_1.payload = {"media_id": "m1", "project_id": "p1"}

        mock_result_2 = MagicMock()
        mock_result_2.id = "point2"
        mock_result_2.score = 0.85
        mock_result_2.payload = {"media_id": "m2", "project_id": "p1"}

        self.mock_client.search.return_value = [mock_result_1, mock_result_2]

        results = qdrant_mod.search_similar(
            collection="clip_embeddings",
            query_vector=[0.1] * 512,
            limit=20,
        )

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["point_id"], "point1")
        self.assertEqual(results[0]["score"], 0.95)
        self.assertEqual(results[0]["media_id"], "m1")
        self.assertEqual(results[1]["point_id"], "point2")

    def test_search_with_project_filter(self):
        self.mock_client.search.return_value = []

        qdrant_mod.search_similar(
            collection="clip_embeddings",
            query_vector=[0.1] * 512,
            project_id="project123",
        )

        call_args = self.mock_client.search.call_args
        self.assertIsNotNone(call_args[1].get('query_filter'))

    def test_search_without_filter(self):
        self.mock_client.search.return_value = []

        qdrant_mod.search_similar(
            collection="clip_embeddings",
            query_vector=[0.1] * 512,
        )

        call_args = self.mock_client.search.call_args
        self.assertIsNone(call_args[1].get('query_filter'))

    def test_search_with_media_type_filter(self):
        self.mock_client.search.return_value = []

        qdrant_mod.search_similar(
            collection="clip_embeddings",
            query_vector=[0.1] * 512,
            media_types=["image", "video"],
        )

        call_args = self.mock_client.search.call_args
        self.assertIsNotNone(call_args[1].get('query_filter'))

    def test_search_empty_results(self):
        self.mock_client.search.return_value = []

        results = qdrant_mod.search_similar(
            collection="clip_embeddings",
            query_vector=[0.1] * 512,
        )

        self.assertEqual(results, [])

    def test_search_respects_limit(self):
        self.mock_client.search.return_value = []

        qdrant_mod.search_similar(
            collection="clip_embeddings",
            query_vector=[0.1] * 512,
            limit=5,
        )

        call_args = self.mock_client.search.call_args
        self.assertEqual(call_args[1]['limit'], 5)

    def test_search_respects_score_threshold(self):
        self.mock_client.search.return_value = []

        qdrant_mod.search_similar(
            collection="clip_embeddings",
            query_vector=[0.1] * 512,
            score_threshold=0.5,
        )

        call_args = self.mock_client.search.call_args
        self.assertEqual(call_args[1]['score_threshold'], 0.5)


class TestSearchById(unittest.TestCase):
    """Tests for search_by_id (recommend) function."""

    def setUp(self):
        self.mock_client = MagicMock()
        qdrant_mod._client = self.mock_client

    def tearDown(self):
        qdrant_mod._client = None

    def test_search_by_id_basic(self):
        mock_result = MagicMock()
        mock_result.id = "point2"
        mock_result.score = 0.88
        mock_result.payload = {"media_id": "m2"}

        self.mock_client.recommend.return_value = [mock_result]

        results = qdrant_mod.search_by_id(
            collection="clip_embeddings",
            point_id="point1",
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["score"], 0.88)
        self.mock_client.recommend.assert_called_once()

    def test_search_by_id_with_project_filter(self):
        self.mock_client.recommend.return_value = []

        qdrant_mod.search_by_id(
            collection="clip_embeddings",
            point_id="point1",
            project_id="proj123",
        )

        call_args = self.mock_client.recommend.call_args
        self.assertIsNotNone(call_args[1].get('query_filter'))


class TestDeletePoint(unittest.TestCase):
    """Tests for delete_point function."""

    def setUp(self):
        self.mock_client = MagicMock()
        qdrant_mod._client = self.mock_client

    def tearDown(self):
        qdrant_mod._client = None

    def test_delete_point(self):
        qdrant_mod.delete_point("clip_embeddings", "point1")
        self.mock_client.delete.assert_called_once()


class TestDeleteByMediaId(unittest.TestCase):
    """Tests for delete_by_media_id function."""

    def setUp(self):
        self.mock_client = MagicMock()
        qdrant_mod._client = self.mock_client

    def tearDown(self):
        qdrant_mod._client = None

    def test_deletes_from_all_collections(self):
        qdrant_mod.delete_by_media_id("media123")

        # Should delete from 3 collections (clip, dino, text)
        self.assertEqual(self.mock_client.delete.call_count, 3)

    def test_handles_delete_errors_gracefully(self):
        self.mock_client.delete.side_effect = Exception("connection error")

        # Should not raise
        qdrant_mod.delete_by_media_id("media123")


if __name__ == '__main__':
    unittest.main()
