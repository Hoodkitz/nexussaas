"""Tenant management endpoints."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import uuid

router = APIRouter(prefix="/api/v1/tenants", tags=["tenants"])

class CreateTenantRequest(BaseModel):
    name: str
    slug: str

class TenantResponse(BaseModel):
    id: str
    name: str
    slug: str

@router.post("", response_model=TenantResponse)
def create_tenant(req: CreateTenantRequest):
    # TODO: persist, set tenant context
    return TenantResponse(id=str(uuid.uuid4()), name=req.name, slug=req.slug)

@router.get("/{tenant_id}", response_model=TenantResponse)
def get_tenant(tenant_id: str):
    # TODO: DB lookup with authorization
    raise HTTPException(status_code=404, detail="Tenant not found")
