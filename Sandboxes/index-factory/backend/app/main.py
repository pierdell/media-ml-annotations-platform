from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import structlog
import os

from app.config import get_settings
from app.api import auth, objects, documents, media, search, categories

logger = structlog.get_logger()
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Index Factory API")
    # Ensure upload directory
    os.makedirs(settings.upload_dir, exist_ok=True)
    # Ensure qdrant collections
    try:
        from app.services.qdrant_service import ensure_collections
        await ensure_collections()
    except Exception as e:
        logger.warning("Qdrant not available at startup, collections will be created later", error=str(e))
    yield
    logger.info("Shutting down Index Factory API")


app = FastAPI(
    title="Index Factory",
    description="Live indexation platform with hybrid search",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(auth.router)
app.include_router(objects.router)
app.include_router(documents.router)
app.include_router(media.router)
app.include_router(search.router)
app.include_router(categories.router)

# Serve uploads
if os.path.isdir(settings.upload_dir):
    app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "index-factory"}
