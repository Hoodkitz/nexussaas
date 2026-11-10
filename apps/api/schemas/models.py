"""Pydantic request/response schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, EmailStr, Field


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)
    name: Optional[str] = Field(default=None, max_length=255)
    tenant_name: Optional[str] = Field(default=None, max_length=255)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)
    tenant_id: Optional[str] = None


class SwitchTenantIn(BaseModel):
    tenant_id: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    tenant_id: Optional[str] = None
    role: Optional[str] = None


class UserOut(BaseModel):
    id: str
    email: str
    name: Optional[str] = None


class MeOut(BaseModel):
    user: UserOut
    tenant_id: Optional[str]
    role: Optional[str]
    tenants: list[dict]


class TenantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: Optional[str] = Field(default=None, max_length=100)


class TenantOut(BaseModel):
    id: str
    name: str
    slug: str
    plan: str
    status: str
    created_at: Optional[datetime] = None


class MemberIn(BaseModel):
    email: EmailStr
    role: Literal["admin", "member", "viewer"] = "member"


class MemberRoleIn(BaseModel):
    role: Literal["owner", "admin", "member", "viewer"]


class MemberOut(BaseModel):
    user_id: str
    email: str
    name: Optional[str]
    role: str


class JobCreate(BaseModel):
    blueprint: dict[str, Any]
    idempotency_key: Optional[str] = Field(default=None, max_length=255)


class JobOut(BaseModel):
    id: str
    status: str
    attempt: int
    trace_id: Optional[str] = None
    artifact_sha256: Optional[str] = None
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class JobDecisionIn(BaseModel):
    approve: bool
    comment: Optional[str] = Field(default=None, max_length=2000)
