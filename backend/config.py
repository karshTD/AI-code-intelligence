"""
config.py — Application Configuration
--------------------------------------
Uses pydantic-settings to load configuration from environment variables or a .env file.
Centralizing config here keeps secrets out of source code and makes the app
easy to configure in different deployment environments (local, Docker, cloud).
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    # ── Server ────────────────────────────────────────────────────────────────
    app_name: str = "AI Code Intelligence Platform"
    app_version: str = "0.1.1"
    debug: bool = False
    port: int = 8000
    allowed_origins: list[str] = ["*"]  # Tighten for production

    # ── LLM Provider ─────────────────────────────────────────────────────────
    # Set to "groq", "openai", or "anthropic". Falls back to "mock" if no key is found.
    llm_provider: str = "groq"

    # ── Groq ──────────────────────────────────────────────────────────────────
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile" 

    # ── OpenAI ────────────────────────────────────────────────────────────────
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # ── Anthropic ─────────────────────────────────────────────────────────────
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-5-haiku-20241022"

    # Pydantic v2: reads from .env file automatically
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def effective_provider(self) -> str:
        """
        Resolve which LLM provider to actually use.
        Falls back to 'mock' so the system works without API keys (useful for dev/testing).
        """
        if self.llm_provider == "groq" and self.groq_api_key:
            return "groq"
        if self.llm_provider == "openai" and self.openai_api_key:
            return "openai"
        if self.llm_provider == "anthropic" and self.anthropic_api_key:
            return "anthropic"
        return "mock"


@lru_cache
def get_settings() -> Settings:
    """
    Cached singleton — settings are loaded once at startup and reused.
    Using lru_cache means no repeated .env file reads on every request.
    """
    return Settings()