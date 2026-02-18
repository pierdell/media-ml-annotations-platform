"""Security middleware - input sanitization, request validation."""

import re
import time

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger()

# Max request body sizes by content type
_MAX_JSON_BODY = 10 * 1024 * 1024  # 10MB
_MAX_FORM_BODY = 2 * 1024 * 1024 * 1024  # 2GB (for file uploads)

# Paths that don't need rate limiting
_EXEMPT_PATHS = {"/health", "/api/docs", "/api/redoc", "/api/openapi.json"}

# SQL injection patterns
_SQL_INJECTION_RE = re.compile(
    r"(\b(union|select|insert|update|delete|drop|alter|exec|execute|xp_)\b.*\b(from|into|table|where|set)\b)",
    re.IGNORECASE,
)

# XSS patterns
_XSS_RE = re.compile(
    r"(<script|javascript:|on\w+\s*=|<iframe|<object|<embed)",
    re.IGNORECASE,
)


class SecurityMiddleware(BaseHTTPMiddleware):
    """
    Security hardening middleware:
    - Request size validation
    - Basic input sanitization checks
    - Security headers
    - Request timing
    """

    async def dispatch(self, request: Request, call_next):
        # Skip checks for exempt paths
        if request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        # Check Content-Length
        content_length = request.headers.get("content-length")
        if content_length:
            size = int(content_length)
            content_type = request.headers.get("content-type", "")
            if "multipart/form-data" in content_type:
                if size > _MAX_FORM_BODY:
                    return Response(
                        content='{"detail": "Request body too large"}',
                        status_code=413,
                        media_type="application/json",
                    )
            elif size > _MAX_JSON_BODY:
                return Response(
                    content='{"detail": "Request body too large"}',
                    status_code=413,
                    media_type="application/json",
                )

        # Check query parameters for injection
        query_string = str(request.url.query)
        if query_string and (_SQL_INJECTION_RE.search(query_string) or _XSS_RE.search(query_string)):
            logger.warning(
                "suspicious_request",
                path=request.url.path,
                query=query_string[:200],
                ip=request.client.host if request.client else "unknown",
            )
            return Response(
                content='{"detail": "Invalid request parameters"}',
                status_code=400,
                media_type="application/json",
            )

        # Execute request with timing
        start = time.monotonic()
        response = await call_next(request)
        elapsed = time.monotonic() - start

        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Request-Duration"] = f"{elapsed:.3f}"

        # Log slow requests
        if elapsed > 5.0:
            logger.warning(
                "slow_request",
                path=request.url.path,
                method=request.method,
                duration=round(elapsed, 2),
                status=response.status_code,
            )

        return response
