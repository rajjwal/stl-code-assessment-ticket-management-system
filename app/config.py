"""Application configuration via environment variables.

Uses pydantic-settings to load from .env file and validate at startup.
All AI and database settings are centralized here.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    DATABASE_URL: str = "sqlite+aiosqlite:///./cmdb.db"

    # OpenRouter AI configuration
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    AI_MODEL: str = "meta-llama/llama-4-maverick"
    AI_TEMPERATURE: float = 0.1  # Low for deterministic structured output
    AI_MAX_TOKENS: int = 4096


settings = Settings()
