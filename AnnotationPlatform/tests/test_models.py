"""
Unit tests for data models and enums (backend/app/models/).

Tests enum values, model relationships, and data integrity rules.
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
import tests.mock_deps  # noqa: E402

from app.models.media import MediaType, IndexingStatus
from app.models.dataset import DatasetType, DatasetStatus, AnnotationType
from app.models.project import ProjectRole


class TestMediaTypeEnum(unittest.TestCase):
    """Tests for MediaType enum."""

    def test_values(self):
        self.assertEqual(MediaType.IMAGE, "image")
        self.assertEqual(MediaType.VIDEO, "video")
        self.assertEqual(MediaType.AUDIO, "audio")
        self.assertEqual(MediaType.TEXT, "text")
        self.assertEqual(MediaType.DOCUMENT, "document")

    def test_count(self):
        self.assertEqual(len(MediaType), 5)

    def test_string_comparison(self):
        self.assertEqual(MediaType.IMAGE, "image")
        self.assertNotEqual(MediaType.IMAGE, "video")


class TestIndexingStatusEnum(unittest.TestCase):
    """Tests for IndexingStatus enum."""

    def test_values(self):
        self.assertEqual(IndexingStatus.PENDING, "pending")
        self.assertEqual(IndexingStatus.PROCESSING, "processing")
        self.assertEqual(IndexingStatus.COMPLETED, "completed")
        self.assertEqual(IndexingStatus.FAILED, "failed")
        self.assertEqual(IndexingStatus.PARTIAL, "partial")

    def test_count(self):
        self.assertEqual(len(IndexingStatus), 5)


class TestDatasetTypeEnum(unittest.TestCase):
    """Tests for DatasetType enum."""

    def test_values(self):
        self.assertEqual(DatasetType.IMAGE_CLASSIFICATION, "image_classification")
        self.assertEqual(DatasetType.OBJECT_DETECTION, "object_detection")
        self.assertEqual(DatasetType.INSTANCE_SEGMENTATION, "instance_segmentation")
        self.assertEqual(DatasetType.SEMANTIC_SEGMENTATION, "semantic_segmentation")
        self.assertEqual(DatasetType.IMAGE_CAPTIONING, "image_captioning")
        self.assertEqual(DatasetType.VIDEO_CLASSIFICATION, "video_classification")
        self.assertEqual(DatasetType.VIDEO_OBJECT_TRACKING, "video_object_tracking")
        self.assertEqual(DatasetType.AUDIO_CLASSIFICATION, "audio_classification")
        self.assertEqual(DatasetType.SPEECH_RECOGNITION, "speech_recognition")
        self.assertEqual(DatasetType.TEXT_CLASSIFICATION, "text_classification")
        self.assertEqual(DatasetType.NER, "ner")
        self.assertEqual(DatasetType.CUSTOM, "custom")

    def test_count(self):
        self.assertEqual(len(DatasetType), 12)


class TestDatasetStatusEnum(unittest.TestCase):
    """Tests for DatasetStatus enum."""

    def test_values(self):
        self.assertEqual(DatasetStatus.DRAFT, "draft")
        self.assertEqual(DatasetStatus.ACTIVE, "active")
        self.assertEqual(DatasetStatus.FROZEN, "frozen")
        self.assertEqual(DatasetStatus.ARCHIVED, "archived")

    def test_count(self):
        self.assertEqual(len(DatasetStatus), 4)


class TestAnnotationTypeEnum(unittest.TestCase):
    """Tests for AnnotationType enum."""

    def test_values(self):
        self.assertEqual(AnnotationType.BBOX, "bbox")
        self.assertEqual(AnnotationType.POLYGON, "polygon")
        self.assertEqual(AnnotationType.POLYLINE, "polyline")
        self.assertEqual(AnnotationType.POINT, "point")
        self.assertEqual(AnnotationType.MASK, "mask")
        self.assertEqual(AnnotationType.CLASSIFICATION, "classification")
        self.assertEqual(AnnotationType.CAPTION, "caption")
        self.assertEqual(AnnotationType.TRANSCRIPTION, "transcription")
        self.assertEqual(AnnotationType.TEMPORAL_SEGMENT, "temporal_segment")
        self.assertEqual(AnnotationType.CUSTOM, "custom")

    def test_count(self):
        self.assertEqual(len(AnnotationType), 10)


class TestProjectRoleEnum(unittest.TestCase):
    """Tests for ProjectRole enum."""

    def test_values(self):
        self.assertEqual(ProjectRole.OWNER, "owner")
        self.assertEqual(ProjectRole.ADMIN, "admin")
        self.assertEqual(ProjectRole.EDITOR, "editor")
        self.assertEqual(ProjectRole.VIEWER, "viewer")

    def test_count(self):
        self.assertEqual(len(ProjectRole), 4)

    def test_ordering(self):
        # Roles should be comparable as strings
        roles = [ProjectRole.VIEWER, ProjectRole.OWNER, ProjectRole.EDITOR, ProjectRole.ADMIN]
        sorted_roles = sorted(roles)
        self.assertEqual(sorted_roles[0], ProjectRole.ADMIN)


class TestEnumMembership(unittest.TestCase):
    """Tests for enum membership checks."""

    def test_media_type_membership(self):
        self.assertIn("image", [mt.value for mt in MediaType])
        self.assertNotIn("unknown", [mt.value for mt in MediaType])

    def test_indexing_status_membership(self):
        self.assertIn("completed", [s.value for s in IndexingStatus])

    def test_dataset_type_membership(self):
        self.assertIn("object_detection", [dt.value for dt in DatasetType])

    def test_annotation_type_membership(self):
        self.assertIn("bbox", [at.value for at in AnnotationType])
        self.assertIn("polygon", [at.value for at in AnnotationType])


if __name__ == '__main__':
    unittest.main()
