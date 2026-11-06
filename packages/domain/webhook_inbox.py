"""Stripe webhook inbox for idempotent processing."""
import uuid
from sqlalchemy import Column, String, DateTime, Integer, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from packages.storage.db import Base
from datetime import datetime, timezone

class WebhookInbox(Base):
    __tablename__ = "webhook_inbox"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(String(255), unique=True, nullable=False, index=True)
    event_type = Column(String(100), nullable=False)
    status = Column(String(20), default="pending", nullable=False)  # pending, processed, failed, dead_letter
    attempts = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)
    payload = Column(JSONB, nullable=True)
    received_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    processed_at = Column(DateTime(timezone=True), nullable=True)
