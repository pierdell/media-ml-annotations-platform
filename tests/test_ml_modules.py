"""
Unit tests for ML modules (CLIP, DINO, VLM).

Tests model initialization, lazy loading, singleton patterns,
and encoding methods with mocked ML backends.
"""

import sys
import os
import unittest
from unittest.mock import MagicMock, patch, PropertyMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
import tests.mock_deps  # noqa: E402


class TestCLIPEncoder(unittest.TestCase):
    """Tests for the CLIPEncoder class."""

    def setUp(self):
        # Reset singleton
        import app.ml.clip_encoder as clip_mod
        self.clip_mod = clip_mod
        clip_mod._clip_instance = None
        clip_mod._text_instance = None

    def test_init_default_device_cpu(self):
        encoder = self.clip_mod.CLIPEncoder()
        self.assertEqual(encoder.device, "cpu")
        self.assertIsNone(encoder._model)

    def test_init_custom_model(self):
        encoder = self.clip_mod.CLIPEncoder(model_name="ViT-L/14")
        self.assertEqual(encoder.model_name, "ViT-L/14")

    def test_lazy_loading(self):
        encoder = self.clip_mod.CLIPEncoder()
        self.assertIsNone(encoder._model)
        # _load is called on first encoding call

    def test_load_initializes_model(self):
        encoder = self.clip_mod.CLIPEncoder()
        encoder._load()
        self.assertIsNotNone(encoder._model)
        self.assertIsNotNone(encoder._preprocess)
        self.assertIsNotNone(encoder._tokenizer)

    def test_load_called_only_once(self):
        encoder = self.clip_mod.CLIPEncoder()
        with patch('open_clip.create_model_and_transforms') as mock_create:
            mock_model = MagicMock()
            mock_model.to.return_value = mock_model
            mock_model.eval.return_value = mock_model
            mock_create.return_value = (mock_model, None, MagicMock())

            encoder._load()
            encoder._load()  # Second call should be no-op

            mock_create.assert_called_once()

    def test_encode_image_bytes(self):
        encoder = self.clip_mod.CLIPEncoder()
        encoder._model = MagicMock()
        encoder._preprocess = MagicMock(return_value=MagicMock())

        mock_embedding = MagicMock()
        mock_embedding.__truediv__ = MagicMock(return_value=mock_embedding)
        mock_embedding.norm.return_value = MagicMock()
        mock_embedding.squeeze.return_value = MagicMock()
        mock_embedding.squeeze().cpu.return_value = MagicMock()
        mock_embedding.squeeze().cpu().numpy.return_value = MagicMock()
        mock_embedding.squeeze().cpu().numpy().tolist.return_value = [0.1] * 512

        encoder._model.encode_image.return_value = mock_embedding

        with patch('PIL.Image.open', return_value=MagicMock(mode="RGB")):
            result = encoder.encode_image_bytes(b"fake_image_data")

        self.assertEqual(len(result), 512)

    def test_singleton_get_clip_encoder(self):
        e1 = self.clip_mod.get_clip_encoder()
        e2 = self.clip_mod.get_clip_encoder()
        self.assertIs(e1, e2)

    def test_singleton_get_text_encoder(self):
        e1 = self.clip_mod.get_text_encoder()
        e2 = self.clip_mod.get_text_encoder()
        self.assertIs(e1, e2)


class TestTextEncoder(unittest.TestCase):
    """Tests for the TextEncoder class."""

    def setUp(self):
        import app.ml.clip_encoder as clip_mod
        self.clip_mod = clip_mod
        clip_mod._text_instance = None

    def test_init_default_model(self):
        encoder = self.clip_mod.TextEncoder()
        self.assertIsNone(encoder._model)
        self.assertEqual(encoder.model_name, "sentence-transformers/all-MiniLM-L6-v2")

    def test_lazy_loading(self):
        encoder = self.clip_mod.TextEncoder()
        self.assertIsNone(encoder._model)

    def test_load_creates_model(self):
        encoder = self.clip_mod.TextEncoder()
        with patch('sentence_transformers.SentenceTransformer') as mock_st:
            mock_st.return_value = MagicMock()
            encoder._load()
            mock_st.assert_called_once_with(encoder.model_name)

    def test_encode(self):
        encoder = self.clip_mod.TextEncoder()
        mock_model = MagicMock()
        mock_model.encode.return_value = MagicMock(tolist=MagicMock(return_value=[0.1] * 384))
        encoder._model = mock_model

        result = encoder.encode("test query")
        self.assertEqual(result, [0.1] * 384)
        mock_model.encode.assert_called_once_with("test query", normalize_embeddings=True)

    def test_encode_batch(self):
        encoder = self.clip_mod.TextEncoder()
        mock_model = MagicMock()
        mock_model.encode.return_value = MagicMock(
            tolist=MagicMock(return_value=[[0.1] * 384, [0.2] * 384])
        )
        encoder._model = mock_model

        result = encoder.encode_batch(["text1", "text2"])
        self.assertEqual(len(result), 2)


class TestDINOEncoder(unittest.TestCase):
    """Tests for the DINOEncoder class."""

    def setUp(self):
        import app.ml.dino_encoder as dino_mod
        self.dino_mod = dino_mod
        dino_mod._instance = None

    def test_init_default(self):
        encoder = self.dino_mod.DINOEncoder()
        self.assertEqual(encoder.device, "cpu")
        self.assertIsNone(encoder._model)

    def test_custom_model_name(self):
        encoder = self.dino_mod.DINOEncoder(model_name="facebook/dinov2-large")
        self.assertEqual(encoder.model_name, "facebook/dinov2-large")

    def test_lazy_loading(self):
        encoder = self.dino_mod.DINOEncoder()
        self.assertIsNone(encoder._model)
        self.assertIsNone(encoder._transform)

    def test_singleton(self):
        e1 = self.dino_mod.get_dino_encoder()
        e2 = self.dino_mod.get_dino_encoder()
        self.assertIs(e1, e2)

    def test_encode_image(self):
        encoder = self.dino_mod.DINOEncoder()
        encoder._model = MagicMock()
        encoder._transform = MagicMock(return_value=MagicMock())

        mock_features = MagicMock()
        mock_features.__truediv__ = MagicMock(return_value=mock_features)
        mock_features.norm.return_value = MagicMock()
        mock_features.squeeze.return_value = MagicMock()
        mock_features.squeeze().cpu.return_value = MagicMock()
        mock_features.squeeze().cpu().numpy.return_value = MagicMock()
        mock_features.squeeze().cpu().numpy().tolist.return_value = [0.1] * 768

        encoder._model.return_value = mock_features

        mock_image = MagicMock()
        mock_image.mode = "RGB"

        result = encoder.encode_image(mock_image)
        self.assertEqual(len(result), 768)

    def test_encode_image_converts_non_rgb(self):
        encoder = self.dino_mod.DINOEncoder()
        encoder._model = MagicMock()
        encoder._transform = MagicMock(return_value=MagicMock())

        mock_features = MagicMock()
        mock_features.__truediv__ = MagicMock(return_value=mock_features)
        mock_features.norm.return_value = MagicMock()
        mock_features.squeeze.return_value = MagicMock()
        mock_features.squeeze().cpu.return_value = MagicMock()
        mock_features.squeeze().cpu().numpy.return_value = MagicMock()
        mock_features.squeeze().cpu().numpy().tolist.return_value = [0.1] * 768

        encoder._model.return_value = mock_features

        mock_image = MagicMock()
        mock_image.mode = "RGBA"
        mock_image.convert.return_value = MagicMock(mode="RGB")

        encoder.encode_image(mock_image)
        mock_image.convert.assert_called_once_with("RGB")

    def test_encode_image_bytes(self):
        encoder = self.dino_mod.DINOEncoder()
        encoder._model = MagicMock()
        encoder._transform = MagicMock(return_value=MagicMock())

        mock_features = MagicMock()
        mock_features.__truediv__ = MagicMock(return_value=mock_features)
        mock_features.norm.return_value = MagicMock()
        mock_features.squeeze.return_value = MagicMock()
        mock_features.squeeze().cpu.return_value = MagicMock()
        mock_features.squeeze().cpu().numpy.return_value = MagicMock()
        mock_features.squeeze().cpu().numpy().tolist.return_value = [0.1] * 768

        encoder._model.return_value = mock_features

        with patch('PIL.Image.open', return_value=MagicMock(mode="RGB")):
            result = encoder.encode_image_bytes(b"fake_data")
        self.assertEqual(len(result), 768)


class TestVLMService(unittest.TestCase):
    """Tests for the VLMService class."""

    def setUp(self):
        import app.ml.vlm_service as vlm_mod
        self.vlm_mod = vlm_mod
        vlm_mod._instance = None

    def test_init_default(self):
        vlm = self.vlm_mod.VLMService()
        self.assertEqual(vlm.device, "cpu")
        self.assertIsNone(vlm._model)

    def test_lazy_loading(self):
        vlm = self.vlm_mod.VLMService()
        self.assertIsNone(vlm._model)
        self.assertIsNone(vlm._processor)

    def test_singleton(self):
        v1 = self.vlm_mod.get_vlm_service()
        v2 = self.vlm_mod.get_vlm_service()
        self.assertIs(v1, v2)

    def test_generate_caption(self):
        vlm = self.vlm_mod.VLMService()
        vlm._model = MagicMock()
        vlm._processor = MagicMock()

        vlm._processor.return_value = MagicMock()
        vlm._processor().to.return_value = MagicMock()
        vlm._model.generate.return_value = MagicMock()
        vlm._processor.batch_decode.return_value = ["A cat sitting on a mat"]

        mock_image = MagicMock()
        mock_image.mode = "RGB"

        result = vlm.generate_caption(mock_image)
        self.assertEqual(result, "A cat sitting on a mat")

    def test_answer_question(self):
        vlm = self.vlm_mod.VLMService()
        vlm._model = MagicMock()
        vlm._processor = MagicMock()

        vlm._processor.return_value = MagicMock()
        vlm._processor().to.return_value = MagicMock()
        vlm._model.generate.return_value = MagicMock()
        vlm._processor.batch_decode.return_value = ["yes"]

        mock_image = MagicMock()
        mock_image.mode = "RGB"

        result = vlm.answer_question(mock_image, "Is there a cat?")
        self.assertEqual(result, "yes")

    def test_generate_tags(self):
        vlm = self.vlm_mod.VLMService()
        vlm._model = MagicMock()
        vlm._processor = MagicMock()

        vlm._processor.return_value = MagicMock()
        vlm._processor().to.return_value = MagicMock()
        vlm._model.generate.return_value = MagicMock()
        vlm._processor.batch_decode.return_value = ["cat, mat, indoor, sitting"]

        mock_image = MagicMock()
        mock_image.mode = "RGB"

        result = vlm.generate_tags(mock_image)
        self.assertIsInstance(result, list)
        self.assertIn("cat", result)
        self.assertIn("mat", result)
        self.assertIn("indoor", result)
        self.assertIn("sitting", result)

    def test_caption_from_bytes(self):
        vlm = self.vlm_mod.VLMService()
        vlm._model = MagicMock()
        vlm._processor = MagicMock()

        vlm._processor.return_value = MagicMock()
        vlm._processor().to.return_value = MagicMock()
        vlm._model.generate.return_value = MagicMock()
        vlm._processor.batch_decode.return_value = ["A dog"]

        with patch('PIL.Image.open', return_value=MagicMock(mode="RGB")):
            result = vlm.caption_from_bytes(b"fake_image")
        self.assertEqual(result, "A dog")

    def test_tags_from_bytes(self):
        vlm = self.vlm_mod.VLMService()
        vlm._model = MagicMock()
        vlm._processor = MagicMock()

        vlm._processor.return_value = MagicMock()
        vlm._processor().to.return_value = MagicMock()
        vlm._model.generate.return_value = MagicMock()
        vlm._processor.batch_decode.return_value = ["dog, park, sunny"]

        with patch('PIL.Image.open', return_value=MagicMock(mode="RGB")):
            result = vlm.tags_from_bytes(b"fake_image")
        self.assertIn("dog", result)


class TestImageConversionRGB(unittest.TestCase):
    """Tests that non-RGB images are converted before encoding."""

    def test_clip_converts_rgba_to_rgb(self):
        from app.ml.clip_encoder import CLIPEncoder
        encoder = CLIPEncoder()
        encoder._model = MagicMock()
        encoder._preprocess = MagicMock(return_value=MagicMock())

        mock_embedding = MagicMock()
        mock_embedding.__truediv__ = MagicMock(return_value=mock_embedding)
        mock_embedding.norm.return_value = MagicMock()
        mock_embedding.squeeze.return_value = MagicMock()
        mock_embedding.squeeze().cpu.return_value = MagicMock()
        mock_embedding.squeeze().cpu().numpy.return_value = MagicMock()
        mock_embedding.squeeze().cpu().numpy().tolist.return_value = [0.1] * 512

        encoder._model.encode_image.return_value = mock_embedding

        mock_image = MagicMock()
        mock_image.mode = "RGBA"
        mock_image.convert.return_value = MagicMock(mode="RGB")

        encoder.encode_image(mock_image)
        mock_image.convert.assert_called_once_with("RGB")

    def test_vlm_converts_grayscale_to_rgb(self):
        from app.ml.vlm_service import VLMService
        vlm = VLMService()
        vlm._model = MagicMock()
        vlm._processor = MagicMock()
        vlm._processor.return_value = MagicMock()
        vlm._processor().to.return_value = MagicMock()
        vlm._model.generate.return_value = MagicMock()
        vlm._processor.batch_decode.return_value = ["caption"]

        mock_image = MagicMock()
        mock_image.mode = "L"
        mock_image.convert.return_value = MagicMock(mode="RGB")

        vlm.generate_caption(mock_image)
        mock_image.convert.assert_called_once_with("RGB")


if __name__ == '__main__':
    unittest.main()
