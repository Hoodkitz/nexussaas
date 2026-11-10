"""Redis connection (shared pool)."""
from functools import lru_cache

import redis

from packages.settings import settings


@lru_cache
def get_redis() -> "redis.Redis":
    return redis.from_url(settings.REDIS_URL, decode_responses=True, socket_timeout=5)
