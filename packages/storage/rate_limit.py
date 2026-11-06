"""Redis token bucket rate limiter."""
import time
from packages.storage.redis import get_redis

def check_rate_limit(key: str, max_tokens: int, window_seconds: int) -> tuple[bool, int]:
    """Returns (allowed, remaining_tokens)."""
    try:
        r = get_redis()
        now = int(time.time())
        bucket_key = f"rl:{key}:{now // window_seconds}"
        current = r.incr(bucket_key)
        if current == 1:
            r.expire(bucket_key, window_seconds)
        remaining = max(0, max_tokens - current)
        return current <= max_tokens, remaining
    except Exception:
        return True, max_tokens
