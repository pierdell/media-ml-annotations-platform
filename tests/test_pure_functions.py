"""
Unit tests for pure functions that don't need external dependencies.

Tests for:
- worker/tasks/indexing.py: _chunk_text, _export_coco, _export_yolo, _export_csv, _export_jsonl
- backend/app/services/storage.py: compute_sha256
"""

import sys
import os
import unittest
import json
import hashlib

# Setup mocks before importing app code
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
import tests.mock_deps  # noqa: E402


class TestChunkText(unittest.TestCase):
    """Tests for the _chunk_text function from worker/tasks/indexing.py."""

    def setUp(self):
        # Import after mocks are set up
        from worker.tasks.indexing import _chunk_text
        self.chunk_text = _chunk_text

    def test_short_text_returns_single_chunk(self):
        text = "Hello world"
        result = self.chunk_text(text, max_length=512)
        self.assertEqual(result, ["Hello world"])

    def test_exact_max_length_returns_single_chunk(self):
        text = "a" * 512
        result = self.chunk_text(text, max_length=512)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], text)

    def test_long_text_splits_at_sentence_boundaries(self):
        sentences = ["This is sentence one. ", "This is sentence two. ", "This is sentence three. "]
        text = "".join(sentences)
        result = self.chunk_text(text, max_length=30)
        self.assertTrue(len(result) > 1)
        for chunk in result:
            self.assertTrue(len(chunk) > 0)

    def test_empty_text_returns_single_chunk(self):
        result = self.chunk_text("", max_length=512)
        self.assertEqual(result, [""])

    def test_text_with_newlines(self):
        text = "Line one\nLine two\nLine three"
        result = self.chunk_text(text, max_length=512)
        self.assertEqual(len(result), 1)

    def test_very_long_single_sentence_truncated(self):
        text = "word " * 200  # ~1000 chars, no sentence boundary
        result = self.chunk_text(text, max_length=100)
        self.assertTrue(len(result) >= 1)

    def test_multiple_sentences_fit_max_length(self):
        text = "Short. Also short. Very short."
        result = self.chunk_text(text, max_length=512)
        self.assertEqual(len(result), 1)


class TestExportCoco(unittest.TestCase):
    """Tests for the _export_coco function."""

    def setUp(self):
        from worker.tasks.indexing import _export_coco
        self.export_coco = _export_coco

    def _make_data(self, items=None, labels=None):
        return {
            "dataset": "test_dataset",
            "type": "object_detection",
            "version": "v1.0",
            "label_schema": {"labels": labels or []},
            "items": items or [],
        }

    def test_empty_dataset(self):
        data = self._make_data()
        result = json.loads(self.export_coco(data))
        self.assertEqual(result["images"], [])
        self.assertEqual(result["annotations"], [])
        self.assertEqual(result["categories"], [])
        self.assertEqual(result["info"]["description"], "test_dataset")

    def test_with_bbox_annotations(self):
        data = self._make_data(
            labels=[{"id": "person", "name": "Person"}, {"id": "car", "name": "Car"}],
            items=[{
                "media_id": "img001",
                "split": "train",
                "annotations": [{
                    "type": "bbox",
                    "label": "person",
                    "confidence": 0.95,
                    "geometry": {"x": 10, "y": 20, "w": 100, "h": 50},
                    "attributes": {},
                    "frame_number": None,
                }],
            }],
        )
        result = json.loads(self.export_coco(data))
        self.assertEqual(len(result["images"]), 1)
        self.assertEqual(len(result["annotations"]), 1)
        self.assertEqual(len(result["categories"]), 2)

        ann = result["annotations"][0]
        self.assertEqual(ann["bbox"], [10, 20, 100, 50])
        self.assertEqual(ann["area"], 5000)
        self.assertEqual(ann["category_id"], 1)  # person is first

    def test_with_polygon_annotations(self):
        data = self._make_data(
            labels=[{"id": "mask", "name": "Mask"}],
            items=[{
                "media_id": "img002",
                "split": "val",
                "annotations": [{
                    "type": "polygon",
                    "label": "mask",
                    "confidence": 1.0,
                    "geometry": {"points": [[10, 20], [30, 40], [50, 60]]},
                    "attributes": None,
                    "frame_number": None,
                }],
            }],
        )
        result = json.loads(self.export_coco(data))
        ann = result["annotations"][0]
        self.assertEqual(ann["segmentation"], [[10, 20, 30, 40, 50, 60]])

    def test_multiple_images_incremental_ids(self):
        items = [
            {"media_id": f"img{i}", "split": "train", "annotations": []}
            for i in range(5)
        ]
        data = self._make_data(items=items)
        result = json.loads(self.export_coco(data))
        self.assertEqual(len(result["images"]), 5)
        ids = [img["id"] for img in result["images"]]
        self.assertEqual(ids, [1, 2, 3, 4, 5])

    def test_annotation_ids_are_sequential(self):
        items = [{
            "media_id": "img001",
            "split": "train",
            "annotations": [
                {"type": "bbox", "label": "a", "confidence": 1, "geometry": {"x": 0, "y": 0, "w": 10, "h": 10}, "attributes": None, "frame_number": None},
                {"type": "bbox", "label": "b", "confidence": 1, "geometry": {"x": 5, "y": 5, "w": 20, "h": 20}, "attributes": None, "frame_number": None},
            ],
        }]
        data = self._make_data(items=items, labels=[{"name": "a"}, {"name": "b"}])
        result = json.loads(self.export_coco(data))
        ann_ids = [a["id"] for a in result["annotations"]]
        self.assertEqual(ann_ids, [1, 2])


class TestExportYolo(unittest.TestCase):
    """Tests for the _export_yolo function."""

    def setUp(self):
        from worker.tasks.indexing import _export_yolo
        self.export_yolo = _export_yolo

    def test_empty_dataset(self):
        data = {"items": [], "label_schema": {"labels": []}}
        result = self.export_yolo(data)
        self.assertEqual(result, b"")

    def test_bbox_annotations(self):
        data = {
            "label_schema": {"labels": [{"id": "cat", "name": "Cat"}, {"id": "dog", "name": "Dog"}]},
            "items": [{
                "media_id": "img1",
                "split": "train",
                "annotations": [
                    {"type": "bbox", "label": "dog", "geometry": {"x": 0.5, "y": 0.5, "w": 0.3, "h": 0.4}},
                ],
            }],
        }
        result = self.export_yolo(data).decode()
        self.assertIn("1 0.5 0.5 0.3 0.4", result)  # dog is class index 1

    def test_non_bbox_annotations_skipped(self):
        data = {
            "label_schema": {"labels": [{"id": "p", "name": "P"}]},
            "items": [{
                "media_id": "img1",
                "split": "train",
                "annotations": [
                    {"type": "polygon", "label": "p", "geometry": {"points": [[0, 0]]}},
                ],
            }],
        }
        result = self.export_yolo(data)
        self.assertEqual(result, b"")


class TestExportCsv(unittest.TestCase):
    """Tests for the _export_csv function."""

    def setUp(self):
        from worker.tasks.indexing import _export_csv
        self.export_csv = _export_csv

    def test_empty_dataset(self):
        data = {"items": []}
        result = self.export_csv(data).decode()
        lines = result.strip().split("\n")
        self.assertEqual(len(lines), 1)  # header only
        self.assertIn("media_id", lines[0])

    def test_with_annotations(self):
        data = {
            "items": [{
                "media_id": "img1",
                "split": "train",
                "annotations": [{
                    "type": "bbox",
                    "label": "person",
                    "confidence": 0.9,
                    "geometry": {"x": 10, "y": 20, "w": 100, "h": 50},
                }],
            }],
        }
        result = self.export_csv(data).decode()
        lines = result.strip().split("\n")
        self.assertEqual(len(lines), 2)  # header + 1 row
        self.assertIn("person", lines[1])
        self.assertIn("bbox", lines[1])


class TestExportJsonl(unittest.TestCase):
    """Tests for the _export_jsonl function."""

    def setUp(self):
        from worker.tasks.indexing import _export_jsonl
        self.export_jsonl = _export_jsonl

    def test_empty_dataset(self):
        data = {"items": []}
        result = self.export_jsonl(data)
        self.assertEqual(result, b"")

    def test_with_items(self):
        data = {
            "items": [
                {"media_id": "img1", "split": "train", "annotations": [{"type": "bbox"}]},
                {"media_id": "img2", "split": "val", "annotations": []},
            ],
        }
        result = self.export_jsonl(data).decode()
        lines = [l for l in result.strip().split("\n") if l]
        self.assertEqual(len(lines), 2)
        row1 = json.loads(lines[0])
        self.assertEqual(row1["media_id"], "img1")
        self.assertEqual(row1["split"], "train")
        row2 = json.loads(lines[1])
        self.assertEqual(row2["media_id"], "img2")


class TestComputeSha256(unittest.TestCase):
    """Tests for storage.compute_sha256."""

    def setUp(self):
        from app.services.storage import compute_sha256
        self.compute_sha256 = compute_sha256

    def test_known_hash(self):
        expected = hashlib.sha256(b"hello").hexdigest()
        self.assertEqual(self.compute_sha256(b"hello"), expected)

    def test_empty_bytes(self):
        expected = hashlib.sha256(b"").hexdigest()
        self.assertEqual(self.compute_sha256(b""), expected)

    def test_binary_data(self):
        data = bytes(range(256))
        expected = hashlib.sha256(data).hexdigest()
        self.assertEqual(self.compute_sha256(data), expected)

    def test_returns_hex_string(self):
        result = self.compute_sha256(b"test")
        self.assertEqual(len(result), 64)
        self.assertTrue(all(c in '0123456789abcdef' for c in result))


if __name__ == '__main__':
    unittest.main()
