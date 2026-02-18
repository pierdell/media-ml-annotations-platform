"""API route registration."""

from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.projects import router as projects_router
from app.api.media import router as media_router
from app.api.datasets import router as datasets_router
from app.api.search import router as search_router
from app.api.indexing import router as indexing_router
from app.api.ws import router as ws_router
from app.api.active_learning import router as active_learning_router
from app.api.quality import router as quality_router
from app.api.augmentation import router as augmentation_router
from app.api.training import router as training_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(projects_router)
api_router.include_router(media_router)
api_router.include_router(datasets_router)
api_router.include_router(search_router)
api_router.include_router(indexing_router)
api_router.include_router(active_learning_router)
api_router.include_router(quality_router)
api_router.include_router(augmentation_router)
api_router.include_router(training_router)

# WS router registered at root (not under /api/v1 prefix)
ws_api_router = ws_router
