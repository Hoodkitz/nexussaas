"""Redis-based job queue (stub)."""
import json
from packages.storage.redis import get_redis

QUEUE_NAME = "nexussaas:jobs"

def enqueue_job(job_id: str, tenant_id: str, payload: dict):
    r = get_redis()
    r.lpush(QUEUE_NAME, json.dumps({"job_id": job_id, "tenant_id": tenant_id, "payload": payload}))

def dequeue_job():
    r = get_redis()
    item = r.rpop(QUEUE_NAME)
    if item:
        return json.loads(item)
    return None
