"""DINOv2 model wrapper for visual feature extraction."""

import io

import numpy as np
import structlog
import torch
from PIL import Image
from torchvision import transforms

from app.config import get_settings

logger = structlog.get_logger()
settings = get_settings()


class DINOEncoder:
    """Encodes images using DINOv2 for fine-grained visual features."""

    def __init__(self, model_name: str | None = None, device: str | None = None):
        self.model_name = model_name or settings.DINO_MODEL_NAME
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self._model = None
        self._transform = None

    def _load(self):
        if self._model is not None:
            return

        logger.info("loading_dino_model", model=self.model_name, device=self.device)

        self._model = torch.hub.load("facebookresearch/dinov2", "dinov2_vitb14")
        self._model = self._model.to(self.device).eval()

        self._transform = transforms.Compose([
            transforms.Resize(256, interpolation=transforms.InterpolationMode.BICUBIC),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])

        logger.info("dino_model_loaded", model=self.model_name)

    def encode_image(self, image: Image.Image) -> list[float]:
        """Encode a PIL Image to a DINOv2 feature vector (CLS token)."""
        self._load()
        if image.mode != "RGB":
            image = image.convert("RGB")

        tensor = self._transform(image).unsqueeze(0).to(self.device)

        with torch.no_grad():
            features = self._model(tensor)

        # Normalize
        features = features / features.norm(dim=-1, keepdim=True)
        return features.squeeze().cpu().numpy().tolist()

    def encode_image_bytes(self, data: bytes) -> list[float]:
        """Encode raw image bytes."""
        image = Image.open(io.BytesIO(data))
        return self.encode_image(image)

    def encode_batch(self, images: list[Image.Image]) -> list[list[float]]:
        """Encode a batch of images."""
        self._load()
        tensors = torch.stack([
            self._transform(img.convert("RGB") if img.mode != "RGB" else img)
            for img in images
        ]).to(self.device)

        with torch.no_grad():
            features = self._model(tensors)
            features = features / features.norm(dim=-1, keepdim=True)

        return features.cpu().numpy().tolist()

    def encode_image_patches(self, image: Image.Image) -> np.ndarray:
        """Get patch-level features (useful for segmentation/attention)."""
        self._load()
        if image.mode != "RGB":
            image = image.convert("RGB")

        tensor = self._transform(image).unsqueeze(0).to(self.device)

        with torch.no_grad():
            # Get intermediate features with patches
            features = self._model.get_intermediate_layers(tensor, n=1)[0]

        return features.squeeze().cpu().numpy()


_instance: DINOEncoder | None = None


def get_dino_encoder() -> DINOEncoder:
    global _instance
    if _instance is None:
        _instance = DINOEncoder()
    return _instance
