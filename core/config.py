"""Application configuration, loaded from environment variables / .env.

Every setting is documented in .env.example. Secrets are never defaulted;
collectors whose keys are absent are automatically disabled rather than failing.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Runtime ---
    environment: str = "development"
    log_level: str = "INFO"

    # --- LLM provider selection ---
    llm_provider: str = "anthropic"  # anthropic | openai | gemini
    llm_model: str = "claude-sonnet-5"
    anthropic_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    gemini_api_key: SecretStr | None = None

    # --- Data provider keys (collector auto-disabled when key is None) ---
    firecrawl_api_key: SecretStr | None = None
    serpapi_api_key: SecretStr | None = None
    crunchbase_api_key: SecretStr | None = None
    newsapi_api_key: SecretStr | None = None
    github_token: SecretStr | None = None

    # --- SEC EDGAR requires a descriptive User-Agent, not a key ---
    sec_edgar_user_agent: str = "InvestmentResearchAssistant research@example.com"

    # --- Budgets & timeouts ---
    max_cost_per_job_usd: float = Field(default=5.0, gt=0)
    collector_timeout_seconds: float = Field(default=90.0, gt=0)
    stage_timeout_seconds: float = Field(default=300.0, gt=0)

    # --- Storage ---
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ira"
    redis_url: str = "redis://localhost:6379/0"


@lru_cache
def get_settings() -> Settings:
    return Settings()
