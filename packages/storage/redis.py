"""Redis connection."""
import os
import redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

def get_redis():
    return redis.from_url(REDIS_URL, decode_responses=True)
