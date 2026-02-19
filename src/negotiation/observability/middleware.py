"""Request ID middleware for HTTP request tracing.

Ensures every HTTP response includes an ``X-Request-ID`` header (either echoed
from the client or auto-generated) and binds the ID into structlog contextvars
so all log entries for the request share the same ``request_id`` field.
"""

from __future__ import annotations

import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Attach a unique request ID to every HTTP request/response cycle."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Process the request, binding a request ID to structlog contextvars.

        If the client sends an ``X-Request-ID`` header, it is reused; otherwise
        a new UUID4 is generated.  The ID is bound to structlog contextvars for
        the duration of the request and set on the response header.

        Args:
            request: The incoming HTTP request.
            call_next: The next middleware or route handler.

        Returns:
            The HTTP response with ``X-Request-ID`` header set.
        """
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id, service="negotiation-agent")
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
