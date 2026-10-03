"""Structured JSON logging with sensitive information redaction."""

import logging
import re
import sys
from collections.abc import MutableMapping
from typing import Any

import structlog

REDACT_PATTERNS = [
    re.compile(r"(api[_-]?key[\"']?\s*[:=]\s*[\"'])([^\"']+)([\"'])", re.IGNORECASE),
    re.compile(r"(bearer\s+)([a-zA-Z0-9_\-\.]{8,})", re.IGNORECASE),
    re.compile(r"(password[\"']?\s*[:=]\s*[\"'])([^\"']+)([\"'])", re.IGNORECASE),
]


def redact_secrets(
    logger: Any, method_name: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    """Censor sensitive tokens and keys in log outputs."""
    event = event_dict.get("event")
    if isinstance(event, str):
        for pattern in REDACT_PATTERNS:
            event = pattern.sub(
                r"\1[REDACTED]\3" if pattern.groups == 3 else r"\1[REDACTED]", event
            )
        event_dict["event"] = event
    return event_dict


def setup_logging(log_level: str = "INFO") -> None:
    """Configure standard and structlog processors."""
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper(), logging.INFO),
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            redact_secrets,
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


logger = structlog.get_logger("clipforge")
