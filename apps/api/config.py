"""Application configuration."""
import os

class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://nexussaas:nexussaas@localhost:5432/nexussaas")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-in-production")
    ENV: str = os.getenv("ENV", "development")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

settings = Settings()
