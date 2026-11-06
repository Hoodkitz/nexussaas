"""Pydantic schemas for API request/response."""
from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime

class TenantCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=100)

class TenantOut(BaseModel):
    id: str
    name: str
    slug: str
    created_at: Optional[datetime] = None

class JobCreate(BaseModel):
    blueprint: Optional[dict] = None
    idempotency_key: Optional[str] = None

class JobOut(BaseModel):
    id: str
    status: str
    attempt: int
    trace_id: Optional[str] = None

class LoginIn(BaseModel):
    email: str
    password: str

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"

class WebhookIn(BaseModel):
    event_id: str
    event_type: str
    payload: Any = None
