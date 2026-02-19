"""Vision-Language Model service for captioning and indexing."""

import io

import structlog
import torch
from PIL import Image

from app.config import get_settings

logger = structlog.get_logger()
settings = get_settings()


class VLMService:
    """
    Uses BLIP-2 or similar VLM for:
    - Auto-captioning images
    - Answering questions about images (VQA)
    - Custom prompt-based indexing
    """

    def __init__(self, model_name: str | None = None, device: str | None = None):
        self.model_name = model_name or settings.VLM_MODEL_NAME
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self._model = None
        self._processor = None

    def _load(self):
        if self._model is not None:
            return

        logger.info("loading_vlm_model", model=self.model_name, device=self.device)
        from transformers import AutoProcessor, Blip2ForConditionalGeneration

        self._processor = AutoProcessor.from_pretrained(self.model_name)

        # Load in 8-bit for memory efficiency on GPU, or float32 on CPU
        if self.device == "cuda":
            self._model = Blip2ForConditionalGeneration.from_pretrained(
                self.model_name,
                torch_dtype=torch.float16,
                device_map="auto",
            )
        else:
            self._model = Blip2ForConditionalGeneration.from_pretrained(
                self.model_name,
                torch_dtype=torch.float32,
            ).to(self.device)

        logger.info("vlm_model_loaded", model=self.model_name)

    def generate_caption(self, image: Image.Image, max_length: int = 100) -> str:
        """Generate a descriptive caption for an image."""
        self._load()
        if image.mode != "RGB":
            image = image.convert("RGB")

        inputs = self._processor(images=image, return_tensors="pt").to(self.device)

        with torch.no_grad():
            generated_ids = self._model.generate(**inputs, max_new_tokens=max_length)

        caption = self._processor.batch_decode(generated_ids, skip_special_tokens=True)[0].strip()
        return caption

    def answer_question(self, image: Image.Image, question: str, max_length: int = 100) -> str:
        """Answer a question about an image (VQA)."""
        self._load()
        if image.mode != "RGB":
            image = image.convert("RGB")

        inputs = self._processor(images=image, text=question, return_tensors="pt").to(self.device)

        with torch.no_grad():
            generated_ids = self._model.generate(**inputs, max_new_tokens=max_length)

        answer = self._processor.batch_decode(generated_ids, skip_special_tokens=True)[0].strip()
        return answer

    def run_custom_prompt(self, image: Image.Image, prompt: str, max_length: int = 200) -> str:
        """Run a custom prompt on an image for flexible indexing."""
        self._load()
        if image.mode != "RGB":
            image = image.convert("RGB")

        inputs = self._processor(images=image, text=prompt, return_tensors="pt").to(self.device)

        with torch.no_grad():
            generated_ids = self._model.generate(**inputs, max_new_tokens=max_length)

        result = self._processor.batch_decode(generated_ids, skip_special_tokens=True)[0].strip()
        return result

    def generate_tags(self, image: Image.Image) -> list[str]:
        """Generate descriptive tags for an image."""
        prompt = "List the main objects, actions, and attributes visible in this image as comma-separated tags:"
        result = self.run_custom_prompt(image, prompt, max_length=150)
        tags = [tag.strip().lower() for tag in result.split(",") if tag.strip()]
        return tags

    def caption_from_bytes(self, data: bytes) -> str:
        """Generate caption from raw image bytes."""
        image = Image.open(io.BytesIO(data))
        return self.generate_caption(image)

    def tags_from_bytes(self, data: bytes) -> list[str]:
        """Generate tags from raw image bytes."""
        image = Image.open(io.BytesIO(data))
        return self.generate_tags(image)


_instance: VLMService | None = None


def get_vlm_service() -> VLMService:
    global _instance
    if _instance is None:
        _instance = VLMService()
    return _instance
