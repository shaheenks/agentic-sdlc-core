"""Structured JSON logging for Cloud Logging, and tagged audit records."""

import json
import logging
import os
import sys
from datetime import UTC, datetime

AUDIT_TAG = "sdlc_audit"
AUDIT_LOGGER = "sdlc.audit"
# Standard LogRecord attributes, and uvicorn's duplicate message with terminal colour codes.
_RESERVED = set(vars(logging.makeLogRecord({}))) | {"color_message"}


class JsonFormatter(logging.Formatter):
    """One JSON object per line, with the keys Cloud Logging understands."""

    def __init__(self, service: str) -> None:
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "severity": record.levelname,
            "message": record.getMessage(),
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "logger": record.name,
            "service": self.service,
        }
        entry.update({k: v for k, v in vars(record).items() if k not in _RESERVED and not k.startswith("_")})
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


def configure_logging(service: str) -> None:
    """Send all logging to stdout as JSON lines, tagged with the service name."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter(service))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(os.environ.get("LOG_LEVEL", "INFO").upper())


def audit(event: str, **fields: object) -> None:
    """Write one audit record. Never pass tokens, secrets or tool argument values."""
    logging.getLogger(AUDIT_LOGGER).info(event, extra={"log_type": AUDIT_TAG, "event": event, **fields})
