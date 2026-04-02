"""
services/analysis_service.py — Analysis Service Layer
-------------------------------------------------------
The service layer sits between the API route and the analysis engine.

Responsibilities:
  - Input validation and normalization (e.g. languageId aliases)
  - Guard clauses (code too large, unsupported language warnings)
  - Calling the AnalysisEngine
  - Any cross-cutting concerns: timing, logging with request context

Why not put this in the route?
  Routes know about HTTP. Services know about the domain. Separating them means
  the same analysis logic can be triggered from, e.g., a CLI or a background job
  without dragging in FastAPI. It also makes the service trivially unit-testable.
"""

from __future__ import annotations

from api.models.schemas import AnalysisRequest, AnalysisResult
from analysis.engine import AnalysisEngine
from analysis.language_registry import LanguageRegistry
from utils.helpers import normalize_language_id, is_code_too_large, sanitize_file_path, timed
from utils.logging import get_logger

logger = get_logger(__name__)

# Module-level default engine instance (created once, shared across requests).
# Routes/tests can override this via dependency injection.
_default_engine = AnalysisEngine()


class AnalysisService:
    """
    Business logic for snippet analysis.
    Constructed per-dependency-injection call so the engine can be swapped in tests.
    """

    def __init__(self, engine: AnalysisEngine | None = None) -> None:
        self._engine = engine or _default_engine

    async def analyze(self, request: AnalysisRequest) -> AnalysisResult:
        """
        Full analysis lifecycle:
          1. Normalize and validate inputs
          2. Delegate to AnalysisEngine
          3. Return the result (no HTTP concerns here)
        """
        # ── Input normalization ───────────────────────────────────────────────
        language = normalize_language_id(request.language)
        if language != request.language:
            logger.info("Normalized languageId %r → %r", request.language, language)

        # Sanitize optional file path for safe display in logs/output
        file_path = sanitize_file_path(request.file_path)

        # ── Guard: code size ──────────────────────────────────────────────────
        if is_code_too_large(request.code):
            logger.warning("Code snippet exceeds size limit — truncation recommended")

        # ── Guard: unsupported language (soft warning, not an error) ──────────
        if not LanguageRegistry.is_supported(language):
            logger.warning(
                "Language %r not in registry — regex fallback will be used. "
                "Supported: %s",
                language,
                LanguageRegistry.supported_languages(),
            )

        normalized_request = AnalysisRequest(
            code=request.code,
            language=language,
            file_path=file_path,
            analyze_full_file=request.analyze_full_file,
        )

        logger.info(
            "AnalysisService.analyze | language=%s | file=%s | code_len=%d",
            language,
            file_path or "<no path>",
            len(request.code),
        )

        # ── Delegate to engine ────────────────────────────────────────────────
        with timed("analysis_pipeline"):
            result = await self._engine.run(normalized_request)

        logger.info(
            "Analysis complete | complexity=%s | provider=%s",
            result.complexity.estimate,
            result.provider_used,
        )

        return result
