"""
Unit tests for the indexing service (backend/app/services/indexing.py).

Tests indexing dispatch, stats, and status updates.
"""

import sys
import os
import uuid
import unittest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
import tests.mock_deps  # noqa: E402

from app.services import indexing as indexing_mod


class TestGetIndexingStats(unittest.IsolatedAsyncioTestCase):
    """Tests for get_indexing_stats function."""

    async def test_returns_correct_structure(self):
        mock_db = AsyncMock()
        project_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.all.return_value = [
            ("completed", 50),
            ("pending", 10),
            ("processing", 5),
            ("failed", 2),
            ("partial", 3),
        ]
        mock_db.execute.return_value = mock_result

        stats = await indexing_mod.get_indexing_stats(mock_db, project_id)

        self.assertEqual(stats["total_media"], 70)
        self.assertEqual(stats["indexed"], 50)
        self.assertEqual(stats["pending"], 10)
        self.assertEqual(stats["processing"], 5)
        self.assertEqual(stats["failed"], 2)
        self.assertEqual(stats["partial"], 3)

    async def test_empty_project(self):
        mock_db = AsyncMock()
        project_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_db.execute.return_value = mock_result

        stats = await indexing_mod.get_indexing_stats(mock_db, project_id)

        self.assertEqual(stats["total_media"], 0)
        self.assertEqual(stats["indexed"], 0)
        self.assertEqual(stats["pending"], 0)

    async def test_missing_status_defaults_to_zero(self):
        mock_db = AsyncMock()
        project_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.all.return_value = [
            ("completed", 10),
        ]
        mock_db.execute.return_value = mock_result

        stats = await indexing_mod.get_indexing_stats(mock_db, project_id)

        self.assertEqual(stats["indexed"], 10)
        self.assertEqual(stats["failed"], 0)
        self.assertEqual(stats["pending"], 0)


class TestMarkMediaIndexed(unittest.IsolatedAsyncioTestCase):
    """Tests for mark_media_indexed function."""

    async def test_marks_completed(self):
        mock_db = AsyncMock()
        media_id = uuid.uuid4()

        # We need to import IndexingStatus
        from app.models.media import IndexingStatus

        await indexing_mod.mark_media_indexed(mock_db, media_id)

        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()

    async def test_marks_with_custom_status(self):
        mock_db = AsyncMock()
        media_id = uuid.uuid4()

        from app.models.media import IndexingStatus

        await indexing_mod.mark_media_indexed(
            mock_db, media_id, status=IndexingStatus.FAILED
        )

        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()


class TestDispatchIndexing(unittest.IsolatedAsyncioTestCase):
    """Tests for dispatch_indexing function."""

    async def test_no_items_returns_empty(self):
        mock_db = AsyncMock()
        project_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalars.return_value = MagicMock()
        mock_result.scalars().all.return_value = []
        mock_db.execute.return_value = mock_result

        result = await indexing_mod.dispatch_indexing(mock_db, project_id)

        self.assertIsNone(result["job_id"])
        self.assertEqual(result["total_items"], 0)

    async def test_dispatches_tasks_for_items(self):
        mock_db = AsyncMock()
        project_id = uuid.uuid4()

        mock_item = MagicMock()
        mock_item.id = uuid.uuid4()
        mock_item.storage_path = "project/media.jpg"
        mock_item.media_type = "image"

        mock_result = MagicMock()
        mock_result.scalars.return_value = MagicMock()
        mock_result.scalars().all.return_value = [mock_item]
        mock_db.execute.return_value = mock_result

        # Mock the celery tasks
        with patch.dict('sys.modules', {
            'worker.tasks.indexing': MagicMock(),
        }):
            result = await indexing_mod.dispatch_indexing(mock_db, project_id)

        self.assertEqual(result["total_items"], 1)
        self.assertEqual(result["status"], "dispatched")

    async def test_custom_pipelines(self):
        mock_db = AsyncMock()
        project_id = uuid.uuid4()

        mock_item = MagicMock()
        mock_item.id = uuid.uuid4()
        mock_item.storage_path = "project/media.jpg"
        mock_item.media_type = "image"

        mock_result = MagicMock()
        mock_result.scalars.return_value = MagicMock()
        mock_result.scalars().all.return_value = [mock_item]
        mock_db.execute.return_value = mock_result

        with patch.dict('sys.modules', {
            'worker.tasks.indexing': MagicMock(),
        }):
            result = await indexing_mod.dispatch_indexing(
                mock_db, project_id, pipelines=["clip"]
            )

        self.assertIn("clip", result["pipelines"])
        self.assertEqual(len(result["pipelines"]), 1)


if __name__ == '__main__':
    unittest.main()
