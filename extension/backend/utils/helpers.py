"""
utils/helpers.py — General-Purpose Backend Utilities
------------------------------------------------------
Small, pure helper functions shared across the backend.
Keeping them here (rather than scattered in domain modules) avoids circular
imports and makes them easy to unit-test in isolation.
"""

from __future__ import annotations
import re
import time
import hashlib
from contextlib import contextmanager
from typing import Generator

from utils.logging import get_logger

logger = get_logger(__name__)


# ── Text utilities ────────────────────────────────────────────────────────────

def truncate(text: str, max_chars: int, suffix: str = "…") -> str:
    """Safely truncate a string without splitting mid-word if possible."""
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars - len(suffix)]
    # Step back to the last whitespace to avoid splitting a token
    last_space = cut.rfind(" ")
    if last_space > max_chars // 2:
        cut = cut[:last_space]
    return cut + suffix


def normalize_language_id(language_id: str) -> str:
    """
    Normalize VS Code languageId strings to the canonical form used by the registry.
    E.g. 'javascriptreact' → 'javascript', 'typescriptreact' → 'typescript'.
    """
    _aliases: dict[str, str] = {
        "javascriptreact": "javascript",
        "typescriptreact": "typescript",
        "py":              "python",
        "js":              "javascript",
        "ts":              "typescript",
    }
    return _aliases.get(language_id.lower(), language_id.lower())


def extract_first_function_name(code: str) -> str:
    """
    Quick heuristic to pull the first function name from a snippet.
    Used for error messages and mock output labeling.
    """
    m = re.search(r"(?:def|function|const|async function)\s+(\w+)", code)
    return m.group(1) if m else "unknown"


def code_fingerprint(code: str) -> str:
    """
    Return a short, stable hash of a code snippet.
    Useful as a cache key or for change detection without storing the full snippet.
    """
    return hashlib.sha256(code.encode("utf-8")).hexdigest()[:12]


# ── Timing utility ────────────────────────────────────────────────────────────

@contextmanager
def timed(label: str) -> Generator[None, None, None]:
    """
    Context manager that logs the elapsed time of a block.

    Usage:
        with timed("ast_parse"):
            result = parser.parse(...)
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info("Timing | %s completed in %.1f ms", label, elapsed_ms)


# ── Validation helpers ────────────────────────────────────────────────────────

def is_code_too_large(code: str, max_chars: int = 50_000) -> bool:
    """Guard against accidentally sending enormous files to the LLM."""
    return len(code) > max_chars


def sanitize_file_path(path: str | None) -> str | None:
    """Strip any leading path separators that could hint at directory traversal."""
    if path is None:
        return None
    # Remove leading slashes and Windows drive letters for safe display
    return re.sub(r"^[/\\]+|^[A-Za-z]:[/\\]", "", path)
