"""Structured JSON logging with request/tenant/trace context."""
from __future__ import annotations

import contextvars
import json
import logging
import sys
from datetime import datetime, timezone

request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)
tenant_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("tenant_id", default=None)
trace_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("trace_id", default=None)


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key, var in (("request_id", request_id_var), ("tenant_id", tenant_id_var), ("trace_id", trace_id_var)):
            val = getattr(record, key, None) or var.get()
            if val:
                log[key] = val
        extra = getattr(record, "fields", None)
        if isinstance(extra, dict):
            log.update(extra)
        if record.exc_info:
            log["exception"] = self.formatException(record.exc_info)
        return json.dumps(log, default=str)


_configured = False


def setup_logging(level: str = "INFO") -> logging.Logger:
    global _configured
    root = logging.getLogger()
    if not _configured:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        root.handlers = [handler]
        _configured = True
    root.setLevel(level)
    for noisy in ("uvicorn.access", "httpx", "httpx2", "httpcore"):
        logging.getLogger(noisy).setLevel("WARNING")
    return root
