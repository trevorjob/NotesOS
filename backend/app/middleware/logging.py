"""
Request/response logging middleware.

Adds a unique X-Request-ID to every request and logs:
  - Incoming: method, path
  - Outgoing: method, path, status code, duration (ms)
"""

import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.logging import get_logger

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        t0 = time.monotonic()
        response = await call_next(request)
        duration_ms = round((time.monotonic() - t0) * 1000, 1)

        # Skip noisy health/root pings from logs
        if request.url.path not in ("/health", "/"):
            logger.info(
                "%s %s %s",
                request.method,
                request.url.path,
                response.status_code,
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                },
            )

        response.headers["X-Request-ID"] = request_id
        return response
