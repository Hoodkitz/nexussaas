"""Central configuration, read from the environment (and .env in development)."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env", override=False)


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


class Settings:
    def __init__(self) -> None:
        self.ENV = os.getenv("ENV", "development")
        # Application role: no superuser, no BYPASSRLS -> RLS applies.
        self.DATABASE_URL = os.getenv(
            "DATABASE_URL", "postgresql+psycopg2://nexus_app:nexus_app@localhost:5432/nexussaas"
        )
        # Owner role: runs migrations only.
        self.MIGRATION_DATABASE_URL = os.getenv(
            "MIGRATION_DATABASE_URL", "postgresql+psycopg2://nexussaas:nexussaas@localhost:5432/nexussaas"
        )
        self.APP_DB_PASSWORD = os.getenv("APP_DB_PASSWORD", "nexus_app")
        self.REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.SECRET_KEY = os.getenv("SECRET_KEY", "")
        self.ACCESS_TOKEN_MINUTES = int(os.getenv("ACCESS_TOKEN_MINUTES", "60"))
        self.CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
        self.PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")

        self.GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
        self.GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
        self.GOOGLE_REDIRECT_URI = os.getenv(
            "GOOGLE_REDIRECT_URI", "http://localhost:8000/api/v1/auth/google/callback"
        )

        self.STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
        self.STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
        self.STRIPE_PRICE_PRO = os.getenv("STRIPE_PRICE_PRO", "")

        self.STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local")  # local | s3
        self.STORAGE_LOCAL_DIR = os.getenv("STORAGE_LOCAL_DIR", str(ROOT / "var" / "objects"))
        self.S3_BUCKET = os.getenv("S3_BUCKET", "nexussaas-artifacts")
        self.S3_ENDPOINT = os.getenv("S3_ENDPOINT", "")
        self.S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "")
        self.S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "")

        self.SANDBOX_IMAGE = os.getenv("SANDBOX_IMAGE", "nexussaas-sandbox:latest")
        self.SANDBOX_RUNTIME = os.getenv("SANDBOX_RUNTIME", "")  # e.g. runsc (gVisor)
        self.SANDBOX_TIMEOUT = int(os.getenv("SANDBOX_TIMEOUT", "120"))
        self.SANDBOX_WORKDIR = os.getenv("SANDBOX_WORKDIR", str(ROOT / "var" / "sandbox"))
        self.SANDBOX_ENABLED = _bool("SANDBOX_ENABLED", True)

        self.RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "120"))
        self.RATE_LIMIT_AUTH_PER_MINUTE = int(os.getenv("RATE_LIMIT_AUTH_PER_MINUTE", "10"))
        self.PILOT_MODE = _bool("PILOT_MODE", False)
        self.PILOT_ALLOWED_EMAILS = {
            e.strip().lower() for e in os.getenv("PILOT_ALLOWED_EMAILS", "").split(",") if e.strip()
        }
        self.JOB_MAX_ATTEMPTS = int(os.getenv("JOB_MAX_ATTEMPTS", "3"))
        # Outbound mail (e-mail verification): console | smtp | recording
        self.MAIL_BACKEND = os.getenv("MAIL_BACKEND", "console")
        self.MAIL_FROM = os.getenv("MAIL_FROM", "NexusSaaS <no-reply@localhost>")
        self.SMTP_HOST = os.getenv("SMTP_HOST", "")
        self.SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
        self.SMTP_USER = os.getenv("SMTP_USER", "")
        self.SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
        self.SMTP_STARTTLS = _bool("SMTP_STARTTLS", True)
        self.SMTP_SSL = _bool("SMTP_SSL", False)
        self.EMAIL_VERIFY_HOURS = int(os.getenv("EMAIL_VERIFY_HOURS", "24"))
        self.REQUIRE_VERIFIED_EMAIL = _bool("REQUIRE_VERIFIED_EMAIL", False)
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

        if not self.SECRET_KEY:
            if self.ENV == "production":
                raise RuntimeError("SECRET_KEY must be set in production")
            self.SECRET_KEY = "dev-only-insecure-secret-key-change-me-0123456789"
        if self.ENV == "production" and len(self.SECRET_KEY) < 32:
            raise RuntimeError("SECRET_KEY must be at least 32 characters")
        if self.ENV == "production" and self.MAIL_BACKEND not in ("smtp", "console"):
            raise RuntimeError("MAIL_BACKEND must be smtp (or console) in production")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
