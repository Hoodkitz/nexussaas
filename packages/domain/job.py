"""Job domain model."""
import uuid
from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import enum
from packages.storage.db import Base
from datetime import datetime, timezone

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

class Job(Base):
    __tablename__ = "jobs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    status = Column(SAEnum(JobStatus), default=JobStatus.RECEIVED, nullable=False)
    blueprint = Column(JSONB, nullable=True)
    artifact_ref = Column(String(512), nullable=True)
    attempt = Column(Integer, default=0)
    trace_id = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), onupdate=lambda: datetime.now(timezone.utc))
