"""FastAPI application entry point."""

import structlog
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from app.api import api_router
from app.config import get_settings
from app.database import async_session, engine
from app.models import Base
from app.services.auth import ensure_admin_user

settings = get_settings()
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    logger.info("startup", environment=settings.ENVIRONMENT)

    # Create tables (in production, use alembic migrate instead)
    if settings.ENVIRONMENT == "development":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    # Ensure admin user exists
    async with async_session() as db:
        await ensure_admin_user(db)

    # Initialize Qdrant collections
    try:
        from app.services.qdrant_service import ensure_collections
        ensure_collections()
        logger.info("qdrant_collections_ready")
    except Exception as e:
        logger.warning("qdrant_init_failed", error=str(e))

    yield

    # Shutdown
    await engine.dispose()
    logger.info("shutdown")


app = FastAPI(
    title="Index Factory API",
    description="ML Dataset Creation Platform - Media indexing, search, and annotation",
    version="0.1.0",
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
    docs_url="/api/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/api/redoc" if settings.ENVIRONMENT != "production" else None,
)

# CORS
origins = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(api_router)


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "0.1.0"}


@app.get("/api/v1/status")
async def api_status():
    """Aggregate system status."""
    status = {"api": "ok"}

    # Check DB
    try:
        async with async_session() as db:
            await db.execute("SELECT 1")  # type: ignore
        status["database"] = "ok"
    except Exception:
        status["database"] = "error"

    # Check Redis
    try:
        import redis as redis_lib
        r = redis_lib.from_url(settings.REDIS_URL)
        r.ping()
        status["redis"] = "ok"
    except Exception:
        status["redis"] = "error"

    # Check Qdrant
    try:
        from app.services.qdrant_service import get_qdrant_client
        client = get_qdrant_client()
        client.get_collections()
        status["qdrant"] = "ok"
    except Exception:
        status["qdrant"] = "error"

    return status
