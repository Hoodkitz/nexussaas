"""HTTP middleware: request id, logging context, metrics, rate limiting, security headers."""
from __future__ import annotations

import logging
import time
import uuid

import jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from packages.observability.logging import request_id_var, tenant_id_var
from packages.observability.metrics import HTTP_LATENCY, HTTP_REQUESTS, RATE_LIMITED
from packages.security.tokens import decode_access_token
from packages.settings import settings
from packages.storage.rate_limit import check_rate_limit

log = logging.getLogger("nexus.http")
EXEMPT = {"/healthz", "/readyz", "/metrics"}


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _subject(request: Request) -> tuple[str, str | None]:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        try:
            claims = decode_access_token(auth[7:])
            return f"user:{claims['sub']}", claims.get("tid")
        except jwt.PyJWTError:
            pass
    return f"ip:{_client_ip(request)}", None


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex
        rid_token = request_id_var.set(rid[:64])
        path = request.url.path
        subject, tid = _subject(request)
        tid_token = tenant_id_var.set(tid)
        start = time.perf_counter()
        try:
            if path not in EXEMPT:
                if path.startswith("/api/v1/auth/"):
                    scope, key, limit = "auth", f"auth:ip:{_client_ip(request)}", settings.RATE_LIMIT_AUTH_PER_MINUTE
                else:
                    scope, key, limit = "api", f"api:{tid or subject}", settings.RATE_LIMIT_PER_MINUTE
                allowed, remaining = check_rate_limit(key, limit, 60)
                if not allowed:
                    RATE_LIMITED.labels(scope).inc()
                    return JSONResponse({"detail": "Zu viele Anfragen"}, status_code=429,
                                        headers={"Retry-After": "60", "X-Request-ID": rid})
            response = await call_next(request)
            route = request.scope.get("route")
            route_path = getattr(route, "path", "unmatched")
            elapsed = time.perf_counter() - start
            HTTP_REQUESTS.labels(request.method, route_path, str(response.status_code)).inc()
            HTTP_LATENCY.labels(request.method, route_path).observe(elapsed)
            response.headers["X-Request-ID"] = rid
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Referrer-Policy"] = "no-referrer"
            if path not in EXEMPT:
                log.info("request", extra={"fields": {
                    "method": request.method, "path": path, "status": response.status_code,
                    "ms": round(elapsed * 1000, 1)}})
            return response
        finally:
            request_id_var.reset(rid_token)
            tenant_id_var.reset(tid_token)
