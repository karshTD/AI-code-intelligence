"""
schemas.py — Pydantic Request/Response Models
----------------------------------------------
Defining all data shapes here (not inline in routes) keeps the API contract
explicit and makes it easy to version or extend models independently.
"""

from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


# ── Request ───────────────────────────────────────────────────────────────────

class AnalysisRequest(BaseModel):
    """
    Payload sent by the VS Code extension when the user triggers analysis.
    'language' follows VS Code's languageId convention (e.g. 'python', 'javascript').
    """
    code: str = Field(..., min_length=1, description="Source code snippet to analyze")
    language: str = Field(..., description="Language ID (python, javascript, typescript, etc.)")
    file_path: Optional[str] = Field(None, description="Optional source file path for context")
    analyze_full_file: bool = Field(False, description="If true, treat code as a full file for summarization")


class FileSummaryRequest(BaseModel):
    """Payload for full-file summarization (README generation)."""
    content: str = Field(..., min_length=1)
    language: str
    file_path: Optional[str] = None


# ── Sub-models ────────────────────────────────────────────────────────────────

class FunctionInfo(BaseModel):
    """Represents a detected function/method in the AST."""
    name: str
    start_line: int
    end_line: int
    parameters: list[str] = []
    is_recursive: bool = False


class ASTSummary(BaseModel):
    """Structured summary extracted from the Tree-sitter parse tree."""
    functions: list[FunctionInfo] = []
    loop_count: int = 0
    max_loop_depth: int = 0
    conditional_count: int = 0
    has_recursion: bool = False
    language: str = ""
    node_count: int = 0


class ComplexityInfo(BaseModel):
    """
    Heuristic complexity estimate derived from AST structure.
    We use Big-O notation as a string because it may include symbolic notation (e.g. O(n log n)).
    """
    estimate: str = Field(..., description="Big-O estimate (e.g. O(n²))")
    reasoning: str = Field(..., description="Human-readable explanation of how the estimate was derived")
    confidence: str = Field("medium", description="low | medium | high")


# ── Response ──────────────────────────────────────────────────────────────────

class AnalysisResult(BaseModel):
    """
    The full analysis result returned to the VS Code extension.
    All fields are always present; empty strings indicate unavailable data.
    """
    documentation: str = Field(..., description="Auto-generated docstring/documentation comment")
    complexity: ComplexityInfo
    explanation: str = Field(..., description="Plain-English explanation of what the code does")
    ast_summary: ASTSummary
    provider_used: str = Field("mock", description="Which LLM provider was used (or 'mock')")


class FileSummaryResult(BaseModel):
    """Result of full-file summarization."""
    summary: str
    suggested_readme: str
    detected_exports: list[str] = []
    provider_used: str = "mock"


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    llm_provider: str
