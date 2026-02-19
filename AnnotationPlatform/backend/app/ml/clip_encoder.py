"""CLIP model wrapper for image and text embeddings."""

import io
from functools import lru_cache

import numpy as np
import structlog
import torch
from PIL import Image

from app.config import get_settings

logger = structlog.get_logger()
settings = get_settings()


class CLIPEncoder:
    """Encodes images and text using OpenCLIP models."""

    def __init__(self, model_name: str | None = None, device: str | None = None):
        self.model_name = model_name or settings.CLIP_MODEL_NAME
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self._model = None
        self._preprocess = None
        self._tokenizer = None

    def _load(self):
        if self._model is not None:
            return
        import open_clip

        logger.info("loading_clip_model", model=self.model_name, device=self.device)

        model, _, preprocess = open_clip.create_model_and_transforms(
            self.model_name, pretrained="openai"
        )
        model = model.to(self.device).eval()
        tokenizer = open_clip.get_tokenizer(self.model_name)

        self._model = model
        self._preprocess = preprocess
        self._tokenizer = tokenizer
        logger.info("clip_model_loaded", model=self.model_name)

    def encode_image(self, image: Image.Image) -> list[float]:
        """Encode a PIL Image to a CLIP embedding vector."""
        self._load()
        if image.mode != "RGB":
            image = image.convert("RGB")

        image_tensor = self._preprocess(image).unsqueeze(0).to(self.device)

        with torch.no_grad(), torch.amp.autocast(self.device):
            embedding = self._model.encode_image(image_tensor)
            embedding = embedding / embedding.norm(dim=-1, keepdim=True)

        return embedding.squeeze().cpu().numpy().tolist()

    def encode_image_bytes(self, data: bytes) -> list[float]:
        """Encode raw image bytes."""
        image = Image.open(io.BytesIO(data))
        return self.encode_image(image)

    def encode_text(self, text: str) -> list[float]:
        """Encode text to a CLIP embedding vector."""
        self._load()
        tokens = self._tokenizer([text]).to(self.device)

        with torch.no_grad(), torch.amp.autocast(self.device):
            embedding = self._model.encode_text(tokens)
            embedding = embedding / embedding.norm(dim=-1, keepdim=True)

        return embedding.squeeze().cpu().numpy().tolist()

    def encode_batch_images(self, images: list[Image.Image]) -> list[list[float]]:
        """Encode a batch of images."""
        self._load()
        tensors = torch.stack([
            self._preprocess(img.convert("RGB") if img.mode != "RGB" else img)
            for img in images
        ]).to(self.device)

        with torch.no_grad(), torch.amp.autocast(self.device):
            embeddings = self._model.encode_image(tensors)
            embeddings = embeddings / embeddings.norm(dim=-1, keepdim=True)

        return embeddings.cpu().numpy().tolist()


class TextEncoder:
    """Sentence-transformers based text encoder for hybrid search."""

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or settings.TEXT_EMBEDDING_MODEL
        self._model = None

    def _load(self):
        if self._model is not None:
            return
        from sentence_transformers import SentenceTransformer

        logger.info("loading_text_model", model=self.model_name)
        self._model = SentenceTransformer(self.model_name)
        logger.info("text_model_loaded", model=self.model_name)

    def encode(self, text: str) -> list[float]:
        """Encode text to embedding vector."""
        self._load()
        embedding = self._model.encode(text, normalize_embeddings=True)
        return embedding.tolist()

    def encode_batch(self, texts: list[str]) -> list[list[float]]:
        """Encode batch of texts."""
        self._load()
        embeddings = self._model.encode(texts, normalize_embeddings=True, batch_size=32)
        return embeddings.tolist()


# Singleton instances
_clip_instance: CLIPEncoder | None = None
_text_instance: TextEncoder | None = None


def get_clip_encoder() -> CLIPEncoder:
    global _clip_instance
    if _clip_instance is None:
        _clip_instance = CLIPEncoder()
    return _clip_instance


def get_text_encoder() -> TextEncoder:
    global _text_instance
    if _text_instance is None:
        _text_instance = TextEncoder()
    return _text_instance
