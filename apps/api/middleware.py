"""Tenant context middleware for RLS."""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

class TenantContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Extract tenant_id from JWT or header
        tenant_id = request.headers.get("X-Tenant-ID")
        if tenant_id:
            request.state.tenant_id = tenant_id
        response = await call_next(request)
        return response
