"""
Tests for new features: WebSocket, Active Learning, Quality Control,
Augmentation, Training, Billing, Security, Observability.
"""

import sys
import os
import uuid
import json
import math
import unittest
from unittest.mock import MagicMock, AsyncMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
import tests.mock_deps  # noqa: E402

from tests.mock_deps import get_http_exception_class

HTTPException = get_http_exception_class()


# ═══════════════════════════════════════════════════════════
# WebSocket Connection Manager
# ═══════════════════════════════════════════════════════════

class TestWebSocketConnectionManager(unittest.IsolatedAsyncioTestCase):
    """Test the WebSocket connection manager."""

    def setUp(self):
        from app.services.websocket import ConnectionManager
        self.manager = ConnectionManager()

    async def test_connect_project(self):
        ws = AsyncMock()
        await self.manager.connect_project(ws, "proj1", "user1", "Alice")

        ws.accept.assert_called_once()
        users = self.manager._get_project_users("proj1")
        self.assertEqual(len(users), 1)
        self.assertEqual(users[0]["name"], "Alice")

    async def test_disconnect_project(self):
        ws = AsyncMock()
        await self.manager.connect_project(ws, "proj1", "user1", "Alice")
        self.manager.disconnect_project("proj1", "user1")

        users = self.manager._get_project_users("proj1")
        self.assertEqual(len(users), 0)

    async def test_broadcast_project(self):
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        await self.manager.connect_project(ws1, "proj1", "user1", "Alice")
        await self.manager.connect_project(ws2, "proj1", "user2", "Bob")

        # Reset mocks from the connect calls
        ws1.send_json.reset_mock()
        ws2.send_json.reset_mock()

        await self.manager.broadcast_project("proj1", {"type": "test"}, exclude="user1")

        ws1.send_json.assert_not_called()
        ws2.send_json.assert_called_once_with({"type": "test"})

    async def test_connect_annotation_session(self):
        ws = AsyncMock()
        await self.manager.connect_annotation(ws, "item1", "user1", "Alice")

        users = self.manager.get_annotation_users("item1")
        self.assertEqual(len(users), 1)

    async def test_multiple_users_in_project(self):
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        ws3 = AsyncMock()
        await self.manager.connect_project(ws1, "proj1", "user1", "Alice")
        await self.manager.connect_project(ws2, "proj1", "user2", "Bob")
        await self.manager.connect_project(ws3, "proj1", "user3", "Charlie")

        users = self.manager._get_project_users("proj1")
        self.assertEqual(len(users), 3)

        self.manager.disconnect_project("proj1", "user2")
        users = self.manager._get_project_users("proj1")
        self.assertEqual(len(users), 2)

    async def test_disconnect_nonexistent_project(self):
        """Disconnecting from a project that doesn't exist should not raise."""
        self.manager.disconnect_project("nonexistent", "user1")

    async def test_disconnect_nonexistent_annotation(self):
        """Disconnecting from an annotation session that doesn't exist should not raise."""
        self.manager.disconnect_annotation("nonexistent", "user1")

    async def test_broadcast_empty_project(self):
        """Broadcasting to an empty project should not raise."""
        await self.manager.broadcast_project("empty", {"type": "test"})

    async def test_broadcast_removes_dead_connections(self):
        ws1 = AsyncMock()
        ws2 = AsyncMock()

        # First connect without errors
        await self.manager.connect_project(ws1, "proj1", "user1", "Alice")
        # For user2, manually add to avoid connect_project triggering broadcast
        self.manager._project_connections.setdefault("proj1", {})["user2"] = ws2
        self.manager._user_info["user2"] = {"name": "Bob", "id": "user2"}

        # Now make ws2 fail on send
        ws2.send_json.side_effect = Exception("Connection closed")

        await self.manager.broadcast_project("proj1", {"type": "test"})

        # user2 should be disconnected due to error
        users = self.manager._get_project_users("proj1")
        self.assertEqual(len(users), 1)
        self.assertEqual(users[0]["name"], "Alice")


# ═══════════════════════════════════════════════════════════
# Quality Control - IoU & Agreement (pure functions)
# ═══════════════════════════════════════════════════════════

class TestQualityControlHelpers(unittest.TestCase):
    """Test quality control computation functions."""

    def test_bbox_iou_perfect_overlap(self):
        from app.services.quality_metrics import bbox_iou
        b1 = {"x": 0, "y": 0, "w": 100, "h": 100}
        b2 = {"x": 0, "y": 0, "w": 100, "h": 100}
        iou = bbox_iou(b1, b2)
        self.assertAlmostEqual(iou, 1.0, places=4)

    def test_bbox_iou_no_overlap(self):
        from app.services.quality_metrics import bbox_iou
        b1 = {"x": 0, "y": 0, "w": 50, "h": 50}
        b2 = {"x": 100, "y": 100, "w": 50, "h": 50}
        iou = bbox_iou(b1, b2)
        self.assertAlmostEqual(iou, 0.0, places=4)

    def test_bbox_iou_partial_overlap(self):
        from app.services.quality_metrics import bbox_iou
        b1 = {"x": 0, "y": 0, "w": 100, "h": 100}
        b2 = {"x": 50, "y": 50, "w": 100, "h": 100}
        iou = bbox_iou(b1, b2)
        expected = 2500 / 17500
        self.assertAlmostEqual(iou, expected, places=3)

    def test_label_agreement_perfect(self):
        from app.services.quality_metrics import compute_label_agreement
        annotations = [
            {"user_id": "u1", "label": "cat"},
            {"user_id": "u2", "label": "cat"},
        ]
        score = compute_label_agreement(annotations)
        self.assertAlmostEqual(score, 1.0, places=4)

    def test_label_agreement_disagreement(self):
        from app.services.quality_metrics import compute_label_agreement
        annotations = [
            {"user_id": "u1", "label": "cat"},
            {"user_id": "u2", "label": "dog"},
        ]
        score = compute_label_agreement(annotations)
        self.assertAlmostEqual(score, 0.0, places=4)

    def test_percent_agreement_matching(self):
        from app.services.quality_metrics import compute_percent_agreement
        annotations = [
            {"user_id": "u1", "label": "cat"},
            {"user_id": "u2", "label": "cat"},
        ]
        score = compute_percent_agreement(annotations)
        self.assertEqual(score, 1.0)

    def test_percent_agreement_non_matching(self):
        from app.services.quality_metrics import compute_percent_agreement
        annotations = [
            {"user_id": "u1", "label": "cat"},
            {"user_id": "u2", "label": "dog"},
        ]
        score = compute_percent_agreement(annotations)
        self.assertEqual(score, 0.0)

    def test_iou_agreement_with_bboxes(self):
        from app.services.quality_metrics import compute_iou_agreement
        annotations = [
            {"user_id": "u1", "type": "bbox", "geometry": {"x": 10, "y": 10, "w": 50, "h": 50}},
            {"user_id": "u2", "type": "bbox", "geometry": {"x": 10, "y": 10, "w": 50, "h": 50}},
        ]
        score = compute_iou_agreement(annotations)
        self.assertAlmostEqual(score, 1.0, places=4)

    def test_single_annotator_returns_full_agreement(self):
        from app.services.quality_metrics import compute_label_agreement
        annotations = [{"user_id": "u1", "label": "cat"}]
        score = compute_label_agreement(annotations)
        self.assertEqual(score, 1.0)

    def test_three_annotators_partial_agreement(self):
        from app.services.quality_metrics import compute_label_agreement
        annotations = [
            {"user_id": "u1", "label": "cat"},
            {"user_id": "u2", "label": "cat"},
            {"user_id": "u3", "label": "dog"},
        ]
        score = compute_label_agreement(annotations)
        self.assertAlmostEqual(score, 1.0 / 3.0, places=4)


# ═══════════════════════════════════════════════════════════
# Augmentation Geometry Transforms (pure functions)
# ═══════════════════════════════════════════════════════════

class TestAugmentationTransforms(unittest.TestCase):
    """Test augmentation geometry transformations."""

    def test_horizontal_flip_bbox(self):
        from app.services.quality_metrics import transform_geometry
        geom = {"x": 10, "y": 20, "w": 100, "h": 200}
        transforms = [{"type": "horizontal_flip"}]
        result = transform_geometry(geom, "bbox", transforms, width=640, height=480)
        self.assertEqual(result["x"], 640 - 10 - 100)
        self.assertEqual(result["y"], 20)
        self.assertEqual(result["w"], 100)

    def test_vertical_flip_bbox(self):
        from app.services.quality_metrics import transform_geometry
        geom = {"x": 10, "y": 20, "w": 100, "h": 200}
        transforms = [{"type": "vertical_flip"}]
        result = transform_geometry(geom, "bbox", transforms, width=640, height=480)
        self.assertEqual(result["x"], 10)
        self.assertEqual(result["y"], 480 - 20 - 200)

    def test_scale_bbox(self):
        from app.services.quality_metrics import transform_geometry
        geom = {"x": 10, "y": 20, "w": 100, "h": 200}
        transforms = [{"type": "scale", "factor": 2.0}]
        result = transform_geometry(geom, "bbox", transforms, width=640, height=480)
        self.assertEqual(result["x"], 20)
        self.assertEqual(result["y"], 40)
        self.assertEqual(result["w"], 200)
        self.assertEqual(result["h"], 400)

    def test_horizontal_flip_polygon(self):
        from app.services.quality_metrics import transform_geometry
        geom = {"points": [[10, 10], [50, 10], [50, 50]]}
        transforms = [{"type": "horizontal_flip"}]
        result = transform_geometry(geom, "polygon", transforms, width=640, height=480)
        self.assertEqual(result["points"], [[630, 10], [590, 10], [590, 50]])

    def test_no_transforms(self):
        from app.services.quality_metrics import transform_geometry
        geom = {"x": 10, "y": 20, "w": 100, "h": 200}
        result = transform_geometry(geom, "bbox", [], width=640, height=480)
        self.assertEqual(result, geom)

    def test_combined_transforms(self):
        from app.services.quality_metrics import transform_geometry
        geom = {"x": 10, "y": 20, "w": 100, "h": 200}
        transforms = [
            {"type": "horizontal_flip"},
            {"type": "scale", "factor": 0.5},
        ]
        result = transform_geometry(geom, "bbox", transforms, width=640, height=480)
        self.assertEqual(result["x"], 265)
        self.assertEqual(result["y"], 10)
        self.assertEqual(result["w"], 50)
        self.assertEqual(result["h"], 100)


# ═══════════════════════════════════════════════════════════
# Billing Service
# ═══════════════════════════════════════════════════════════

class TestBillingService(unittest.IsolatedAsyncioTestCase):
    """Test billing service - ensure no-op when disabled."""

    async def test_billing_disabled_record_usage_noop(self):
        from app.billing.service import record_usage
        mock_db = AsyncMock()

        with patch('app.billing.service.get_settings') as mock_settings:
            mock_settings.return_value.BILLING_ENABLED = False
            await record_usage(mock_db, uuid.uuid4(), "api_request")

        mock_db.add.assert_not_called()

    async def test_billing_disabled_check_quota_always_allowed(self):
        from app.billing.service import check_quota
        mock_db = AsyncMock()

        with patch('app.billing.service.get_settings') as mock_settings:
            mock_settings.return_value.BILLING_ENABLED = False
            allowed, reason = await check_quota(mock_db, uuid.uuid4(), "api_request")

        self.assertTrue(allowed)
        self.assertEqual(reason, "")

    async def test_billing_disabled_usage_summary(self):
        from app.billing.service import get_usage_summary
        mock_db = AsyncMock()

        with patch('app.billing.service.get_settings') as mock_settings:
            mock_settings.return_value.BILLING_ENABLED = False
            summary = await get_usage_summary(mock_db, uuid.uuid4())

        self.assertFalse(summary["billing_enabled"])

    async def test_billing_disabled_increment_noop(self):
        from app.billing.service import increment_usage
        mock_db = AsyncMock()

        with patch('app.billing.service.get_settings') as mock_settings:
            mock_settings.return_value.BILLING_ENABLED = False
            await increment_usage(mock_db, uuid.uuid4(), "storage_bytes", 1000)

        mock_db.execute.assert_not_called()

    async def test_is_billing_enabled_false(self):
        from app.billing.service import is_billing_enabled

        with patch('app.billing.service.get_settings') as mock_settings:
            mock_settings.return_value.BILLING_ENABLED = False
            self.assertFalse(is_billing_enabled())

    async def test_is_billing_enabled_true(self):
        from app.billing.service import is_billing_enabled

        with patch('app.billing.service.get_settings') as mock_settings:
            mock_settings.return_value.BILLING_ENABLED = True
            self.assertTrue(is_billing_enabled())


# ═══════════════════════════════════════════════════════════
# Training Models & Functions
# ═══════════════════════════════════════════════════════════

class TestTrainingModels(unittest.TestCase):
    """Test training model enums and training helper functions."""

    def test_training_status_values(self):
        from app.models.training import TrainingStatus
        self.assertEqual(TrainingStatus.QUEUED, "queued")
        self.assertEqual(TrainingStatus.TRAINING, "training")
        self.assertEqual(TrainingStatus.COMPLETED, "completed")
        self.assertEqual(TrainingStatus.FAILED, "failed")
        self.assertEqual(TrainingStatus.CANCELLED, "cancelled")

    def test_training_simulate_functions(self):
        from worker.tasks.training import _simulate_training_step, _simulate_validation_step
        train_loss = _simulate_training_step(1, 50)
        val_loss = _simulate_validation_step(1, 50)
        self.assertGreater(train_loss, 0)
        self.assertGreater(val_loss, 0)

        train_early = _simulate_training_step(1, 50)
        train_late = _simulate_training_step(49, 50)
        self.assertGreater(train_early, train_late)

    def test_evaluate_model_returns_metrics(self):
        from worker.tasks.training import _evaluate_model
        metrics = _evaluate_model("image_classifier", [])
        self.assertIn("accuracy", metrics)
        self.assertIn("f1_macro", metrics)

        metrics = _evaluate_model("object_detector", [])
        self.assertIn("mAP_50", metrics)

        metrics = _evaluate_model("clip_finetune", [])
        self.assertIn("image_retrieval_r1", metrics)

    def test_evaluate_model_unknown_type(self):
        from worker.tasks.training import _evaluate_model
        metrics = _evaluate_model("custom", [])
        self.assertIn("accuracy", metrics)


# ═══════════════════════════════════════════════════════════
# Quality Models
# ═══════════════════════════════════════════════════════════

class TestQualityModels(unittest.TestCase):
    """Test quality control model enums."""

    def test_review_status_values(self):
        from app.models.quality import ReviewStatus
        self.assertEqual(ReviewStatus.PENDING, "pending")
        self.assertEqual(ReviewStatus.APPROVED, "approved")
        self.assertEqual(ReviewStatus.REJECTED, "rejected")
        self.assertEqual(ReviewStatus.NEEDS_REVISION, "needs_revision")


# ═══════════════════════════════════════════════════════════
# Security Middleware Patterns
# ═══════════════════════════════════════════════════════════

class TestSecurityPatterns(unittest.TestCase):
    """Test security regex patterns used in middleware."""

    def test_sql_injection_patterns(self):
        from app.middleware.security import _SQL_INJECTION_RE
        self.assertIsNotNone(_SQL_INJECTION_RE.search("SELECT * FROM users WHERE id=1"))
        self.assertIsNotNone(_SQL_INJECTION_RE.search("UNION SELECT password FROM users"))

        self.assertIsNone(_SQL_INJECTION_RE.search("hello world"))
        self.assertIsNone(_SQL_INJECTION_RE.search("search term"))

    def test_xss_patterns(self):
        from app.middleware.security import _XSS_RE
        self.assertIsNotNone(_XSS_RE.search("<script>alert('xss')</script>"))
        self.assertIsNotNone(_XSS_RE.search("javascript:void(0)"))
        self.assertIsNotNone(_XSS_RE.search('<img onerror="evil()">'))

        self.assertIsNone(_XSS_RE.search("hello world"))
        self.assertIsNone(_XSS_RE.search("a cat sitting on a mat"))

    def test_sql_injection_drop_table(self):
        from app.middleware.security import _SQL_INJECTION_RE
        self.assertIsNotNone(_SQL_INJECTION_RE.search("DROP TABLE users"))


# ═══════════════════════════════════════════════════════════
# Billing Models
# ═══════════════════════════════════════════════════════════

class TestBillingModels(unittest.TestCase):
    """Test billing model enums."""

    def test_usage_type_values(self):
        from app.billing.models import UsageType
        self.assertEqual(UsageType.API_REQUEST, "api_request")
        self.assertEqual(UsageType.STORAGE_BYTES, "storage_bytes")
        self.assertEqual(UsageType.COMPUTE_SECONDS, "compute_seconds")
        self.assertEqual(UsageType.TRAINING_SECONDS, "training_seconds")
        self.assertEqual(UsageType.EMBEDDING_GENERATION, "embedding_generation")
        self.assertEqual(UsageType.VLM_INFERENCE, "vlm_inference")

    def test_subscription_tier_values(self):
        from app.billing.models import SubscriptionTier
        self.assertEqual(SubscriptionTier.FREE, "free")
        self.assertEqual(SubscriptionTier.STARTER, "starter")
        self.assertEqual(SubscriptionTier.PROFESSIONAL, "professional")
        self.assertEqual(SubscriptionTier.ENTERPRISE, "enterprise")


# ═══════════════════════════════════════════════════════════
# Observability
# ═══════════════════════════════════════════════════════════

class TestObservability(unittest.TestCase):
    """Test observability configuration."""

    def test_configure_logging_json(self):
        from app.middleware.observability import configure_logging
        configure_logging(log_level="INFO", log_format="json")

    def test_configure_logging_console(self):
        from app.middleware.observability import configure_logging
        configure_logging(log_level="DEBUG", log_format="console")


# ═══════════════════════════════════════════════════════════
# Config
# ═══════════════════════════════════════════════════════════

class TestNewConfigFields(unittest.TestCase):
    """Test new configuration fields."""

    def test_billing_defaults(self):
        from app.config import Settings
        settings = Settings()
        self.assertFalse(settings.BILLING_ENABLED)
        self.assertTrue(settings.RATE_LIMITING_ENABLED)
        self.assertEqual(settings.LOG_LEVEL, "INFO")
        self.assertEqual(settings.LOG_FORMAT, "json")
        self.assertEqual(settings.DEFAULT_STORAGE_QUOTA_GB, 50)
        self.assertEqual(settings.DEFAULT_COMPUTE_QUOTA_HOURS, 100.0)
        self.assertEqual(settings.DEFAULT_API_RATE_LIMIT, 1000)

    def test_stripe_defaults_empty(self):
        from app.config import Settings
        settings = Settings()
        self.assertEqual(settings.STRIPE_SECRET_KEY, "")
        self.assertEqual(settings.STRIPE_WEBHOOK_SECRET, "")

    def test_prometheus_default_disabled(self):
        from app.config import Settings
        settings = Settings()
        self.assertFalse(settings.PROMETHEUS_ENABLED)


if __name__ == '__main__':
    unittest.main()
