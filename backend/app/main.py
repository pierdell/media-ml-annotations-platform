"""FastAPI application entry point."""

import structlog
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from app.api import api_router, ws_api_router
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
    version="0.2.0",
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

# Security middleware
from app.middleware.security import SecurityMiddleware
app.add_middleware(SecurityMiddleware)

# Billing middleware (only when BILLING_ENABLED=true)
if settings.BILLING_ENABLED:
    from app.billing.middleware import BillingMiddleware
    app.add_middleware(BillingMiddleware)
    logger.info("billing_enabled")

# Error handlers
from app.middleware.error_handler import register_error_handlers
register_error_handlers(app)

# Routes
app.include_router(api_router)
app.include_router(ws_api_router)  # WebSocket routes at root level

# Conditionally register billing API routes
if settings.BILLING_ENABLED:
    from app.billing.api import router as billing_router
    app.include_router(billing_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "0.2.0"}


@app.get("/api/v1/status")
async def api_status():
    """Aggregate system status."""
    status = {"api": "ok", "billing_enabled": settings.BILLING_ENABLED}

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
