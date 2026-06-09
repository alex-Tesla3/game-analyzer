"""Bridge Authorization: Bearer to ?token= for legacy API handlers."""

from __future__ import annotations

from urllib.parse import quote

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class BearerTokenQueryBridgeMiddleware(BaseHTTPMiddleware):
    """Copy Bearer JWT into the query string when routes only read ``token=``."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path.startswith("/api/") or path.startswith("/ws/"):
            auth = request.headers.get("authorization") or ""
            if auth.lower().startswith("bearer "):
                bearer = auth[7:].strip()
                if bearer and "token" not in request.query_params:
                    qs = request.scope.get("query_string", b"")
                    token_q = f"token={quote(bearer, safe='')}".encode()
                    request.scope["query_string"] = (
                        (qs + b"&" + token_q) if qs else token_q
                    )
                    if hasattr(request, "_query_params"):
                        delattr(request, "_query_params")
        return await call_next(request)
