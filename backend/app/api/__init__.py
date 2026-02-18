"""API route registration."""

from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.projects import router as projects_router
from app.api.media import router as media_router
from app.api.datasets import router as datasets_router
from app.api.search import router as search_router
from app.api.indexing import router as indexing_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(projects_router)
api_router.include_router(media_router)
api_router.include_router(datasets_router)
api_router.include_router(search_router)
api_router.include_router(indexing_router)
