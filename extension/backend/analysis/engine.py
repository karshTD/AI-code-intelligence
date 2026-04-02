"""
engine.py — Central Analysis Engine
--------------------------------------
The engine is the single coordinator for the full analysis pipeline.
It owns the sequencing: parse → complexity → AI explanation.

Why a separate engine vs. doing this in the route?
  - Routes should only handle HTTP concerns (parsing requests, returning responses).
  - The engine can be invoked from routes, CLI tools, background workers, or tests
    without pulling in any HTTP machinery.
  - It makes the pipeline testable as a unit without spinning up FastAPI.

The engine is stateless; all dependencies (parser, analyzer, AI client) are
injected at construction time so they can be replaced with mocks in tests.
"""

from __future__ import annotations
import logging

from api.models.schemas import (
    AnalysisRequest,
    AnalysisResult,
    ASTSummary,
    ComplexityInfo,
)
from analysis.ast_parser import ASTParser
from analysis.complexity import ComplexityAnalyzer
from analysis.language_registry import LanguageRegistry
from ai.llm_client import LLMClient
from ai.prompts import build_documentation_prompt, build_explanation_prompt

logger = logging.getLogger(__name__)


class AnalysisEngine:
    """
    Orchestrates the full code analysis pipeline.

    Injected dependencies make every step replaceable for testing:
        engine = AnalysisEngine(ast_parser=MockParser(), llm=MockLLM())
    """

    def __init__(
        self,
        ast_parser: ASTParser | None = None,
        complexity_analyzer: ComplexityAnalyzer | None = None,
        llm_client: LLMClient | None = None,
    ) -> None:
        self._parser = ast_parser or ASTParser()
        self._complexity = complexity_analyzer or ComplexityAnalyzer()
        # LLM client is resolved lazily if not injected, so startup stays fast
        # and the factory reads fresh settings (useful if .env is edited at runtime).
        self._llm_client = llm_client

    # ── Public API ────────────────────────────────────────────────────────────

    async def run(self, request: AnalysisRequest) -> AnalysisResult:
        """
        Execute the full pipeline for a code snippet.

        Steps:
            1. AST parse
            2. Complexity estimation
            3. LLM: documentation generation
            4. LLM: plain-English explanation
            5. Assemble and return AnalysisResult
        """
        logger.info("Engine.run | language=%s | code_len=%d", request.language, len(request.code))

        # ── Step 1: Parse ─────────────────────────────────────────────────────
        ast_summary = self._step_parse(request.code, request.language)

        # ── Step 2: Complexity ────────────────────────────────────────────────
        complexity = self._step_complexity(ast_summary)

        # ── Step 3 & 4: AI calls (run sequentially to avoid double billing
        #   on providers that charge per concurrent request; can be parallelised
        #   later with asyncio.gather if latency becomes a concern) ────────────
        llm = self._resolve_llm()
        documentation = await self._step_documentation(request, ast_summary, complexity, llm)
        explanation = await self._step_explanation(request, ast_summary, llm)

        return AnalysisResult(
            documentation=documentation,
            complexity=complexity,
            explanation=explanation,
            ast_summary=ast_summary,
            provider_used=llm.provider_name(),
        )

    # ── Pipeline steps ─────────────────────────────────────────────────────────

    def _step_parse(self, code: str, language: str) -> ASTSummary:
        """Step 1: Resolve language config and parse the AST."""
        lang_config = LanguageRegistry.get(language)
        # lang_config may be None — the parser handles that with a regex fallback
        return self._parser.parse(code=code, language_config=lang_config)

    def _step_complexity(self, ast_summary: ASTSummary) -> ComplexityInfo:
        """Step 2: Estimate Big-O from the AST summary metrics."""
        return self._complexity.estimate(ast_summary)

    async def _step_documentation(
        self,
        request: AnalysisRequest,
        ast_summary: ASTSummary,
        complexity: ComplexityInfo,
        llm: LLMClient,
    ) -> str:
        """Step 3: Generate docstring/JSDoc via LLM."""
        try:
            system, user = build_documentation_prompt(
                code=request.code,
                language=request.language,
                ast_summary=ast_summary,
                complexity=complexity,
            )
            return await llm.complete(system, user, max_tokens=800)
        except Exception as exc:
            logger.warning("Documentation generation failed: %s", exc)
            return f"[Documentation unavailable: {exc}]"

    async def _step_explanation(
        self,
        request: AnalysisRequest,
        ast_summary: ASTSummary,
        llm: LLMClient,
    ) -> str:
        """Step 4: Generate plain-English explanation via LLM."""
        try:
            system, user = build_explanation_prompt(
                code=request.code,
                language=request.language,
                ast_summary=ast_summary,
            )
            return await llm.complete(system, user, max_tokens=600)
        except Exception as exc:
            logger.warning("Explanation generation failed: %s", exc)
            return f"[Explanation unavailable: {exc}]"

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _resolve_llm(self) -> LLMClient:
        """Return the injected client, or lazily create one from config."""
        if self._llm_client is not None:
            return self._llm_client
        from ai.llm_client import get_llm_client
        return get_llm_client()
