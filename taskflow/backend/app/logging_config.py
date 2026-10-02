"""JSON logs for request investigation. Secrets are redacted."""

import json
import logging
import re
from datetime import datetime, timezone

_URL_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9+.-]*://\S+")


def redact(text: str, secret: str = "") -> str:
    """Remove database URLs and an explicit secret from a log string."""
    cleaned = text
    if secret:
        cleaned = cleaned.replace(secret, "***")
    return _URL_RE.sub("***", cleaned)


class JsonFormatter(logging.Formatter):
    """One JSON object per line, with the fields KubeMedic will look for."""

    def __init__(self, service: str) -> None:
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "service": getattr(record, "service", self.service),
            "message": redact(record.getMessage()),
        }
        endpoint = getattr(record, "endpoint", None)
        if endpoint is not None:
            payload["endpoint"] = endpoint
        status_code = getattr(record, "status_code", None)
        if status_code is not None:
            payload["status_code"] = status_code
        duration_ms = getattr(record, "duration_ms", None)
        if duration_ms is not None:
            payload["duration_ms"] = duration_ms
        error = getattr(record, "error", None)
        if error:
            payload["error"] = redact(str(error))
        if record.exc_info:
            payload["exception"] = redact(self.formatException(record.exc_info))
        return json.dumps(payload, default=str)


def configure_logging(level: str, service: str = "taskflow-api") -> logging.Logger:
    logger = logging.getLogger("taskflow")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.propagate = True
    if not any(getattr(handler, "_taskflow", False) for handler in logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter(service))
        handler._taskflow = True  # type: ignore[attr-defined]
        logger.addHandler(handler)
    return logger


def get_logger() -> logging.Logger:
    return logging.getLogger("taskflow")
