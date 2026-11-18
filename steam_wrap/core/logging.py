"""Logging setup.

* Plain or JSON output (``app.log_json``).
* A redaction filter scrubs ``access_token=...`` / ``key=...`` from every
  record, so credentials never reach log files even if a library logs a URL.
* ``httpx``/``httpcore`` are pinned to WARNING because they log full request
  URLs (which carry the user's token) at INFO.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import UTC, datetime
from typing import Any

_SECRET_PATTERN = re.compile(r"(access_token|key|token)=([^&\s\"']+)", re.IGNORECASE)
_BEARER_PATTERN = re.compile(r"(Bearer\s+)[A-Za-z0-9._\-]+", re.IGNORECASE)


def redact(text: str) -> str:
    """Mask credentials that appear in ``text``."""
    text = _SECRET_PATTERN.sub(r"\1=***", text)
    return _BEARER_PATTERN.sub(r"\1***", text)


class RedactingFilter(logging.Filter):
    """Rewrites each record's message with secrets masked."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        redacted = redact(message)
        if redacted != message:
            record.msg = redacted
            record.args = None
        return True


class JsonFormatter(logging.Formatter):
    """One JSON object per line; extra ``record`` attributes are included."""

    _RESERVED = set(vars(logging.makeLogRecord({}))) | {"message", "asctime"}

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in vars(record).items():
            if key not in self._RESERVED and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO", json_output: bool = False) -> None:
    """Configure the root logger. Safe to call more than once."""
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RedactingFilter())
    if json_output:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s"))

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())

    # Route uvicorn's loggers through our handler (and its redaction filter).
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uv_logger = logging.getLogger(name)
        uv_logger.handlers = []
        uv_logger.propagate = True

    # RequestContextMiddleware writes a richer access line (with request ID and
    # duration, without the query string), so uvicorn's own is redundant.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    for noisy in ("httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
