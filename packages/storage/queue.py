"""Reliable Redis work queue.

ready list --BLMOVE--> per-worker processing list --ack--> removed.
Items of workers whose heartbeat expired are moved back to ready (crash recovery).
Delayed retries live in a sorted set and are promoted when due.
"""
from __future__ import annotations

import json
import time
from typing import Optional

import redis

from packages.settings import settings

READY = "nexus:jobs:ready"
DELAYED = "nexus:jobs:delayed"
PROCESSING = "nexus:jobs:processing:"
HEARTBEAT = "nexus:workers:heartbeat:"
LOCK = "nexus:jobs:lock:"


def client() -> redis.Redis:
    # Separate client without socket timeout: BLMOVE blocks.
    return redis.from_url(settings.REDIS_URL, decode_responses=True)


def enqueue(r: redis.Redis, message: dict) -> None:
    r.lpush(READY, json.dumps(message, sort_keys=True))


def enqueue_delayed(r: redis.Redis, message: dict, delay_seconds: float) -> None:
    r.zadd(DELAYED, {json.dumps(message, sort_keys=True): time.time() + delay_seconds})


def promote_delayed(r: redis.Redis) -> int:
    due = r.zrangebyscore(DELAYED, 0, time.time())
    n = 0
    for item in due:
        if r.zrem(DELAYED, item):
            r.lpush(READY, item)
            n += 1
    return n


def take(r: redis.Redis, worker_id: str, timeout: float = 2.0) -> Optional[str]:
    return r.blmove(READY, PROCESSING + worker_id, timeout, "RIGHT", "LEFT")


def ack(r: redis.Redis, worker_id: str, raw: str) -> None:
    r.lrem(PROCESSING + worker_id, 1, raw)


def heartbeat(r: redis.Redis, worker_id: str, ttl: int = 30) -> None:
    r.set(HEARTBEAT + worker_id, str(time.time()), ex=ttl)


def recover_orphans(r: redis.Redis) -> int:
    """Move items from processing lists of dead workers back to ready."""
    moved = 0
    for key in r.scan_iter(PROCESSING + "*"):
        wid = key[len(PROCESSING):]
        if r.exists(HEARTBEAT + wid):
            continue
        while r.lmove(key, READY, "RIGHT", "LEFT"):
            moved += 1
    return moved


def acquire_lock(r: redis.Redis, job_id: str, owner: str, ttl: int) -> bool:
    return bool(r.set(LOCK + job_id, owner, nx=True, ex=ttl))


def release_lock(r: redis.Redis, job_id: str, owner: str) -> None:
    if r.get(LOCK + job_id) == owner:
        r.delete(LOCK + job_id)
