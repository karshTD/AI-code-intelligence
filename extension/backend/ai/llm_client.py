"""
llm_client.py — Groq-Powered LLM Provider
-----------------------------------------
This module handles AI interactions using Groq for high-speed inference.
It includes a MockClient for local testing without API credits.
"""

from __future__ import annotations
import logging
import re
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

# ── Abstract Base ─────────────────────────────────────────────────────────────

class LLMClient(ABC):
    """Minimal interface for LLM interactions."""

    @abstractmethod
    async def complete(self, system: str, user: str, max_tokens: int = 1024) -> str:
        """Send a chat completion request and return the response text."""
        ...

    @abstractmethod
    def provider_name(self) -> str:
        ...

# ── Groq Implementation ───────────────────────────────────────────────────────

class GroqClient(LLMClient):
    """
    Groq implementation using OpenAI-compatible SDK.
    Optimized for LPU inference speed.
    """
    def __init__(self, api_key: str, model: str):
        import openai  
        self._client = openai.AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1" 
        )
        self._model = model

    async def complete(self, system: str, user: str, max_tokens: int = 1024) -> str:
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                max_tokens=max_tokens,
                temperature=0.2,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"Groq API call failed: {e}")
            return f"[Error] Could not generate AI response: {e}"

    def provider_name(self) -> str:
        return f"groq/{self._model}"

# ── Mock Implementation ───────────────────────────────────────────────────────

class MockClient(LLMClient):
    """Produces plausible-looking output using code introspection (No API Key)."""

    async def complete(self, system: str, user: str, max_tokens: int = 1024) -> str:
        fn_matches = re.findall(r"(?:def|function|const)\s+(\w+)", user)
        fn_name = fn_matches[0] if fn_matches else "this_function"

        if any(kw in system.lower() for kw in ["doc", "jsdoc", "documentation"]):
            return self._mock_documentation(fn_name)
        return self._mock_explanation(fn_name)

    def _mock_documentation(self, fn_name: str) -> str:
        return f'"""\n{fn_name} (Mock Docs)\n\nSet GROQ_API_KEY for real AI output.\n"""'

    def _mock_explanation(self, fn_name: str) -> str:
        return f"**Overview**\n\n`{fn_name}` processed via Mock Engine. Add Groq key for AI analysis."

    def provider_name(self) -> str:
        return "mock"

# ── Factory ───────────────────────────────────────────────────────────────────

def get_llm_client() -> LLMClient:
    """Reads settings and returns the Groq or Mock client."""
    from config import get_settings
    settings = get_settings()
    
    # If the user explicitly wants Groq and provided a key
    if settings.effective_provider == "groq" and settings.groq_api_key:
        logger.info("Using Groq provider (%s)", settings.groq_model)
        return GroqClient(api_key=settings.groq_api_key, model=settings.groq_model)

    logger.warning("No Groq API key found — using MockClient.")
    return MockClient()