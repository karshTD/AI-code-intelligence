"""
analysis.py — Analysis API Route  (refactored to use Service Layer)
----------------------------------------------------------------------
This route is now a thin HTTP adapter. Its only responsibilities are:
  1. Accept + validate the HTTP request (Pydantic handles this).
  2. Delegate to the appropriate service.
  3. Return the HTTP response.

Business logic that previously lived here has moved to:
  - services/analysis_service.py     ← snippet analysis pipeline
  - services/documentation_service.py ← doc generation + file summarization

This keeps the route stable even as the analysis pipeline evolves internally.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.models.schemas import (
    AnalysisRequest,
    AnalysisResult,
    FileSummaryRequest,
    FileSummaryResult,
)
from services.analysis_service import AnalysisService
from services.documentation_service import DocumentationService
from utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["analysis"])

# Module-level service instances (effectively singletons for the process lifetime).
# To override in tests: patch these or use FastAPI dependency overrides.
_analysis_service = AnalysisService()
_documentation_service = DocumentationService()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/analyze", response_model=AnalysisResult, summary="Analyze a code snippet")
async def analyze_code(request: AnalysisRequest) -> AnalysisResult:
    """
    Full analysis pipeline: AST parsing → complexity estimation → AI docs + explanation.
    Supports Python, JavaScript, TypeScript, Java. Falls back gracefully for other languages.
    """
    try:
        return await _analysis_service.analyze(request)
    except Exception as exc:
        logger.exception("Unhandled error in /analyze")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/summarize", response_model=FileSummaryResult, summary="Summarize an entire source file")
async def summarize_file(request: FileSummaryRequest) -> FileSummaryResult:
    """Generate a high-level summary and README section for a full source file."""
    try:
        result = await _documentation_service.generate_file_summary(
            content=request.content,
            language=request.language,
        )
        return FileSummaryResult(
            summary=result["summary"],
            suggested_readme=result["readme_section"],
            detected_exports=[],
            provider_used="",
        )
    except Exception as exc:
        logger.exception("Unhandled error in /summarize")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
