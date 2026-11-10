"""SQLAlchemy models. Tenant-scoped tables are protected by RLS (see migrations)."""
from __future__ import annotations

import enum
import uuid

from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from packages.storage.db import Base


class UserRole(str, enum.Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class JobStatus(str, enum.Enum):
    RECEIVED = "RECEIVED"
    SPEC_VALIDATION = "SPEC_VALIDATION"
    BLUEPRINT_APPROVAL = "BLUEPRINT_APPROVAL"
    DDL_GENERATION = "DDL_GENERATION"
    BACKEND_GENERATION = "BACKEND_GENERATION"
    STATIC_CHECKS = "STATIC_CHECKS"
    SANDBOX_TEST = "SANDBOX_TEST"
    SECURITY_REVIEW = "SECURITY_REVIEW"
    HUMAN_RELEASE_APPROVAL = "HUMAN_RELEASE_APPROVAL"
    PACKAGED = "PACKAGED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


TERMINAL_STATUSES = {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.REJECTED}
APPROVAL_STATUSES = {JobStatus.BLUEPRINT_APPROVAL, JobStatus.HUMAN_RELEASE_APPROVAL}


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class Tenant(Base):
    __tablename__ = "tenants"
    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    plan = Column(String(30), nullable=False, default="free")
    status = Column(String(20), nullable=False, default="active")  # active | pilot | suspended
    monthly_job_quota = Column(Integer, nullable=False, default=20)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=True)
    hashed_password = Column(String(255), nullable=True)
    google_sub = Column(String(255), unique=True, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    token_version = Column(Integer, nullable=False, default=0)
    anonymized_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class TenantMembership(Base):
    __tablename__ = "tenant_memberships"
    __table_args__ = (UniqueConstraint("tenant_id", "user_id", name="uq_membership"),)
    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False, default=UserRole.MEMBER.value)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (UniqueConstraint("tenant_id", "idempotency_key", name="uq_job_idempotency"),)
    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(40), nullable=False, default=JobStatus.RECEIVED.value)
    blueprint = Column(JSONB, nullable=False)
    idempotency_key = Column(String(255), nullable=True)
    artifact_ref = Column(String(512), nullable=True)
    artifact_sha256 = Column(String(64), nullable=True)
    result = Column(JSONB, nullable=True)
    error = Column(Text, nullable=True)
    attempt = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=3)
    trace_id = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class JobEvent(Base):
    __tablename__ = "job_events"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(40), nullable=False)
    detail = Column(JSONB, nullable=True)
    actor_id = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_id = Column(UUID(as_uuid=True), nullable=True)
    action = Column(String(100), nullable=False)
    target = Column(String(255), nullable=True)
    detail = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Subscription(Base):
    __tablename__ = "subscriptions"
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True)
    stripe_customer_id = Column(String(255), nullable=True)
    stripe_subscription_id = Column(String(255), nullable=True)
    status = Column(String(40), nullable=False, default="none")
    plan = Column(String(30), nullable=False, default="free")
    current_period_end = Column(DateTime(timezone=True), nullable=True)
    last_event_created = Column(BigInteger, nullable=False, default=0)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# --- System tables (no tenant data of their own; not reachable via tenant APIs) ---

class WebhookInbox(Base):
    __tablename__ = "webhook_inbox"
    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    provider = Column(String(30), nullable=False, default="stripe")
    event_id = Column(String(255), unique=True, nullable=False)
    event_type = Column(String(100), nullable=False)
    event_created = Column(BigInteger, nullable=True)
    status = Column(String(20), nullable=False, default="pending")  # pending|processed|ignored|failed
    attempts = Column(Integer, nullable=False, default=0)
    last_error = Column(Text, nullable=True)
    payload = Column(JSONB, nullable=True)
    received_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    topic = Column(String(100), nullable=False)
    payload = Column(JSONB, nullable=False)
    published_at = Column(DateTime(timezone=True), nullable=True)
    attempts = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
