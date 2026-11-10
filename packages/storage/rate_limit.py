"""Redis sliding-window rate limiter (sorted set per key)."""
from __future__ import annotations

import logging
import time
import uuid

from packages.storage.redis import get_redis

log = logging.getLogger(__name__)

_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
redis.call('ZREMRANGEBYSCORE', key, 0, now - window)
local count = redis.call('ZCARD', key)
if count >= limit then
  return {0, count}
end
redis.call('ZADD', key, now, ARGV[4])
redis.call('PEXPIRE', key, window)
return {1, count + 1}
"""
_script = None


def check_rate_limit(key: str, limit: int, window_seconds: int = 60) -> tuple[bool, int]:
    """Returns (allowed, remaining). Fails open if Redis is unavailable (logged)."""
    global _script
    try:
        r = get_redis()
        if _script is None:
            _script = r.register_script(_LUA)
        now_ms = int(time.time() * 1000)
        allowed, count = _script(keys=[f"rl:{key}"], args=[now_ms, window_seconds * 1000, limit, uuid.uuid4().hex])
        return bool(allowed), max(0, limit - int(count))
    except Exception:  # pragma: no cover - availability over strictness, see ADR/runbook
        log.warning("rate limiter unavailable, failing open")
        return True, limit
