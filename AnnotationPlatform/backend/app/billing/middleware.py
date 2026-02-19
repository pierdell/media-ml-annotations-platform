"""Billing middleware - request-level usage tracking and quota enforcement.

Only active when BILLING_ENABLED=true.
"""

import time
import re
import uuid

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings

logger = structlog.get_logger()

# Patterns that extract project_id from URL paths
_PROJECT_PATH_RE = re.compile(r"/api/v1/projects/([0-9a-f-]{36})")


class BillingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that tracks API usage per project.
    Only active when BILLING_ENABLED=true.
    """

    async def dispatch(self, request: Request, call_next):
        settings = get_settings()

        if not settings.BILLING_ENABLED:
            return await call_next(request)

        start = time.monotonic()

        # Extract project_id from path
        match = _PROJECT_PATH_RE.search(request.url.path)
        project_id = uuid.UUID(match.group(1)) if match else None

        # Check API rate limit
        if project_id:
            from app.billing.service import check_quota
            from app.database import async_session

            async with async_session() as db:
                allowed, reason = await check_quota(db, project_id, "api_request")
                if not allowed:
                    return Response(
                        content=f'{{"detail": "{reason}"}}',
                        status_code=429,
                        media_type="application/json",
                        headers={"Retry-After": "3600"},
                    )

        response = await call_next(request)

        # Record usage
        if project_id and response.status_code < 500:
            elapsed = time.monotonic() - start
            try:
                from app.billing.service import record_usage, increment_usage
                from app.database import async_session

                async with async_session() as db:
                    await record_usage(
                        db, project_id, "api_request",
                        metadata={"method": request.method, "path": request.url.path, "status": response.status_code},
                    )
                    await increment_usage(db, project_id, "api_request")
                    await db.commit()
            except Exception:
                pass  # Don't fail requests due to billing tracking errors

        return response
