"""Structured logging setup."""
import logging, json, sys
from datetime import datetime, timezone

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "tenant_id"):
            log["tenant_id"] = record.tenant_id
        if hasattr(record, "trace_id"):
            log["trace_id"] = record.trace_id
        if record.exc_info:
            log["exception"] = self.formatException(record.exc_info)
        return json.dumps(log)

def setup_logging(level: str = "INFO"):
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)
    return root
