"""
utils/logging.py — Structured Logging Setup
---------------------------------------------
Provides a single `get_logger()` factory that returns a pre-configured logger.
All backend modules should import from here rather than calling
`logging.getLogger(__name__)` directly, so we have one place to control
log format, level, and output destination.

Output format: JSON-compatible key=value pairs that are easy to grep in
production log aggregators (Datadog, CloudWatch, etc.) while still being
human-readable in local terminals.
"""

from __future__ import annotations
import logging
import sys
from typing import Optional


# ── Formatter ─────────────────────────────────────────────────────────────────

class StructuredFormatter(logging.Formatter):
    """
    Emits log records as key=value pairs on a single line.
    Example:
        2026-03-06 11:30:00 | INFO     | analysis.engine | event=engine.run language=python code_len=142
    """

    LEVEL_COLORS = {
        "DEBUG":    "\033[36m",   # cyan
        "INFO":     "\033[32m",   # green
        "WARNING":  "\033[33m",   # yellow
        "ERROR":    "\033[31m",   # red
        "CRITICAL": "\033[35m",   # magenta
    }
    RESET = "\033[0m"

    def __init__(self, use_color: bool = True) -> None:
        super().__init__()
        self._use_color = use_color

    def format(self, record: logging.LogRecord) -> str:
        level = record.levelname
        color = self.LEVEL_COLORS.get(level, "") if self._use_color else ""
        reset = self.RESET if self._use_color else ""

        # Base fields always present
        parts = [
            f"{self.formatTime(record, '%Y-%m-%d %H:%M:%S')}",
            f"{color}{level:<8}{reset}",
            f"{record.name}",
            f"—",
            record.getMessage(),
        ]

        # Append any extra structured fields passed via extra={}
        for key, val in record.__dict__.items():
            if key not in _STANDARD_LOG_ATTRS and not key.startswith("_"):
                parts.append(f"{key}={val!r}")

        line = " | ".join(parts[:4]) + " " + " ".join(parts[4:])

        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)

        return line


_STANDARD_LOG_ATTRS = frozenset(logging.LogRecord.__dict__.keys()) | {
    "message", "asctime", "module", "msecs", "relativeCreated",
    "thread", "threadName", "processName", "process",
}


# ── Public factory ────────────────────────────────────────────────────────────

_configured = False


def configure_logging(level: str = "INFO", use_color: bool = True) -> None:
    """
    Call once at application startup (in main.py) to configure the root logger.
    Subsequent calls are no-ops so importing this module multiple times is safe.
    """
    global _configured
    if _configured:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredFormatter(use_color=use_color))

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.handlers.clear()
    root.addHandler(handler)

    # Silence noisy third-party loggers
    for noisy in ("uvicorn.access", "httpcore", "httpx", "openai._base_client"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _configured = True


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Return a logger instance. Preferred over logging.getLogger() directly
    because it guarantees configure_logging() has been called at least once
    with defaults (useful in tests that don't start the full app).
    """
    if not _configured:
        configure_logging()
    return logging.getLogger(name)
