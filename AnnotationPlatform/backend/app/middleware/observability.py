"""Observability middleware - structured logging, metrics, request tracing."""

import time
import uuid

import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger()

# Paths to exclude from access logging
_QUIET_PATHS = {"/health", "/api/v1/status", "/favicon.ico"}


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds:
    - Request ID tracing (X-Request-ID header)
    - Structured access logging
    - Request duration metrics
    """

    async def dispatch(self, request: Request, call_next):
        # Generate or propagate request ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])

        start = time.monotonic()
        response = await call_next(request)
        duration = time.monotonic() - start

        # Add tracing header to response
        response.headers["X-Request-ID"] = request_id

        # Log access (skip noisy health checks)
        if request.url.path not in _QUIET_PATHS:
            log_data = {
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round(duration * 1000, 1),
                "ip": request.client.host if request.client else "unknown",
            }

            # Get user agent for analytics
            ua = request.headers.get("user-agent", "")
            if ua:
                log_data["user_agent"] = ua[:100]

            if response.status_code >= 500:
                logger.error("request_error", **log_data)
            elif response.status_code >= 400:
                logger.warning("request_client_error", **log_data)
            else:
                logger.info("request", **log_data)

        return response


def configure_logging(log_level: str = "INFO", log_format: str = "json"):
    """
    Configure structured logging with structlog.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_format: 'json' for production, 'console' for development
    """
    import logging
    import sys

    # Set base log level
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper(), logging.INFO),
    )

    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    if log_format == "console":
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        processors.extend([
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ])

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
