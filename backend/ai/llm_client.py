"""
llm_client.py — LLM Provider Abstraction
-----------------------------------------
Follows the Strategy pattern: LLMClient is an abstract base class, and concrete
implementations (OpenAIClient, AnthropicClient, MockClient) are swappable.

The factory function get_llm_client() reads Settings to return the right implementation
at startup. Routes never import specific providers directly — they only use the
LLMClient interface. This makes provider migration a config change, not a code change.

MockClient is NOT a stub — it produces realistic-looking output using code introspection,
making it useful for development and testing without spending API credits.
"""

from __future__ import annotations
import logging
import re
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger(__name__)


# ── Abstract base ─────────────────────────────────────────────────────────────

class LLMClient(ABC):
    """
    Minimal interface for LLM interactions.
    All implementations must produce plain-text responses from a system + user prompt pair.
    """

    @abstractmethod
    async def complete(self, system: str, user: str, max_tokens: int = 1024) -> str:
        """Send a chat completion request and return the response text."""
        ...

    @abstractmethod
    def provider_name(self) -> str:
        ...


# ── OpenAI implementation ─────────────────────────────────────────────────────

class OpenAIClient(LLMClient):
    def __init__(self, api_key: str, model: str):
        import openai  # Lazy import — only loaded when OpenAI is the active provider
        self._client = openai.AsyncOpenAI(api_key=api_key)
        self._model = model

    async def complete(self, system: str, user: str, max_tokens: int = 1024) -> str:
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=max_tokens,
            temperature=0.3,  # Low temperature for deterministic, precise technical output
        )
        return response.choices[0].message.content or ""

    def provider_name(self) -> str:
        return f"openai/{self._model}"


# ── Anthropic implementation ──────────────────────────────────────────────────

class AnthropicClient(LLMClient):
    def __init__(self, api_key: str, model: str):
        import anthropic  # Lazy import
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model

    async def complete(self, system: str, user: str, max_tokens: int = 1024) -> str:
        message = await self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return message.content[0].text if message.content else ""

    def provider_name(self) -> str:
        return f"anthropic/{self._model}"


# ── Mock implementation (offline / no-key fallback) ───────────────────────────

class MockClient(LLMClient):
    """
    Produces plausible-looking output without API calls.
    Useful for development, CI, and demos where API keys aren't available.
    The output is constructed from the code snippet itself, not just hardcoded strings.
    """

    async def complete(self, system: str, user: str, max_tokens: int = 1024) -> str:
        # Extract function names from the prompt for more realistic mock output
        fn_matches = re.findall(r"(?:def|function|const)\s+(\w+)", user)
        fn_name = fn_matches[0] if fn_matches else "this_function"

        if "docstring" in system.lower() or "jsdoc" in system.lower() or "documentation" in system.lower():
            return self._mock_documentation(fn_name, user)
        elif "explain" in system.lower() or "walkthrough" in system.lower():
            return self._mock_explanation(fn_name)
        elif "readme" in system.lower() or "summary" in system.lower():
            return self._mock_summary(fn_name)
        else:
            return f"[Mock LLM] Analysis of `{fn_name}`: No API key configured. Set OPENAI_API_KEY or ANTHROPIC_API_KEY in your .env file."

    def _mock_documentation(self, fn_name: str, prompt: str) -> str:
        # Try to extract complexity from the prompt
        complexity_match = re.search(r"complexity:\s*([^\n]+)", prompt)
        complexity = complexity_match.group(1).strip() if complexity_match else "O(n)"
        return (
            f'"""\n'
            f"{fn_name} — [Mock documentation — configure an LLM API key for real output]\n\n"
            f"Description:\n    Performs the operation implemented by `{fn_name}`.\n\n"
            f"Args:\n    *args: Arguments as defined in the function signature.\n\n"
            f"Returns:\n    Result of the computation.\n\n"
            f"Complexity:\n    {complexity}\n\n"
            f'Example:\n    result = {fn_name}(...)\n"""\n'
            f"\n# ⚠️  Set OPENAI_API_KEY or ANTHROPIC_API_KEY in backend/.env for real AI-generated docs."
        )

    def _mock_explanation(self, fn_name: str) -> str:
        return (
            f"**Overview**\n\n"
            f"`{fn_name}` performs a computation on its inputs. "
            f"(Configure an LLM API key for a detailed plain-English explanation.)\n\n"
            f"**Step-by-step**\n\n"
            f"1. The function receives its arguments.\n"
            f"2. It processes them according to the implemented algorithm.\n"
            f"3. It returns the result.\n\n"
            f"**Note:** This is mock output. Add your API key to `backend/.env` to enable real AI explanations."
        )

    def _mock_summary(self, fn_name: str) -> str:
        return (
            f"## Module Summary\n\n"
            f"This module contains `{fn_name}` and related logic. "
            f"Configure an LLM API key for a detailed AI-generated summary.\n\n"
            f"## Key Exports\n\n- `{fn_name}`\n\n"
            f"## README Section\n\n"
            f"### `{fn_name}`\n\nSee source code for usage details."
        )

    def provider_name(self) -> str:
        return "mock"


# ── Factory ───────────────────────────────────────────────────────────────────

def get_llm_client() -> LLMClient:
    """
    Factory that reads settings and returns the appropriate LLM client.
    Centralizing instantiation here means callers in routes never import
    specific provider modules directly.
    """
    from config import get_settings
    settings = get_settings()
    provider = settings.effective_provider

    if provider == "openai":
        logger.info("Using OpenAI provider (%s)", settings.openai_model)
        return OpenAIClient(api_key=settings.openai_api_key, model=settings.openai_model)

    if provider == "anthropic":
        logger.info("Using Anthropic provider (%s)", settings.anthropic_model)
        return AnthropicClient(api_key=settings.anthropic_api_key, model=settings.anthropic_model)

    logger.warning("No LLM API key found — using MockClient. Set OPENAI_API_KEY in .env to enable AI features.")
    return MockClient()
