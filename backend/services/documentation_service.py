"""
services/documentation_service.py — Documentation Generation Service
----------------------------------------------------------------------
Dedicated service for documentation-only requests.
Separating this from AnalysisService means callers who only want a docstring
don't trigger a full AST + complexity pipeline — they get just what they need.

This also makes the documentation step independently rate-limitable,
cacheable, and testable.
"""

from __future__ import annotations

from api.models.schemas import AnalysisRequest
from analysis.ast_parser import ASTParser
from analysis.complexity import ComplexityAnalyzer
from analysis.language_registry import LanguageRegistry
from ai.llm_client import LLMClient, get_llm_client
from ai.prompts import build_documentation_prompt, build_summarization_prompt
from utils.helpers import normalize_language_id, timed
from utils.logging import get_logger

logger = get_logger(__name__)


class DocumentationService:
    """
    Handles documentation-specific workflows:
      - Single-function docstring generation (from a snippet)
      - Full-file summarization + README suggestion
    """

    def __init__(
        self,
        ast_parser: ASTParser | None = None,
        complexity_analyzer: ComplexityAnalyzer | None = None,
        llm_client: LLMClient | None = None,
    ) -> None:
        self._parser = ast_parser or ASTParser()
        self._complexity = complexity_analyzer or ComplexityAnalyzer()
        self._llm = llm_client  # resolved lazily if None

    async def generate_docstring(self, request: AnalysisRequest) -> str:
        """
        Generate a documentation comment for a code snippet.
        Runs a lightweight parse (AST + complexity) and a single LLM call.
        """
        language = normalize_language_id(request.language)
        lang_config = LanguageRegistry.get(language)

        logger.info("DocumentationService.generate_docstring | language=%s", language)

        with timed("docstring_generation"):
            # We do need AST + complexity so the prompt is accurate
            ast_summary = self._parser.parse(code=request.code, language_config=lang_config)
            complexity = self._complexity.estimate(ast_summary)

            system, user = build_documentation_prompt(
                code=request.code,
                language=language,
                ast_summary=ast_summary,
                complexity=complexity,
            )
            llm = self._resolve_llm()
            return await llm.complete(system, user, max_tokens=800)

    async def generate_file_summary(self, content: str, language: str) -> dict[str, str]:
        """
        Generate a high-level summary + README section for a full source file.

        Returns a dict with keys: 'summary', 'readme_section'.
        Keeping the return type as a dict (rather than a Pydantic model) means
        this service stays decoupled from the HTTP layer's schema definitions.
        """
        language = normalize_language_id(language)
        logger.info("DocumentationService.generate_file_summary | language=%s | size=%d", language, len(content))

        with timed("file_summarization"):
            system, user = build_summarization_prompt(content, language)
            llm = self._resolve_llm()
            raw = await llm.complete(system, user, max_tokens=1200)

        # Minimal parsing of the markdown response
        sections = raw.split("##")
        summary = sections[1].strip() if len(sections) > 1 else raw
        readme_section = sections[-1].strip() if len(sections) > 2 else ""

        return {"summary": summary, "readme_section": readme_section}

    def _resolve_llm(self) -> LLMClient:
        if self._llm is not None:
            return self._llm
        return get_llm_client()
