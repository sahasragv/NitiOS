"""Application configuration loaded from environment variables."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


_BACKEND_DIRECTORY = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime settings for the NitiOS backend application.

    Values are loaded from process environment variables and, when present, the
    ``backend/.env`` file. Environment variables take precedence over file values.
    """

    model_config = SettingsConfigDict(
        env_file=_BACKEND_DIRECTORY / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "NitiOS"
    APP_ENV: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = Field(default=8000, ge=1, le=65535)
    LOG_LEVEL: str = "INFO"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_DEFAULT_MODEL: str = "qwen2.5:3b"
    OLLAMA_TIMEOUT_SECONDS: float = Field(default=60.0, gt=0, le=600)
    MCP_CONFIG_PATH: Path = _BACKEND_DIRECTORY / "mcp_servers.json"
    MCP_TIMEOUT_SECONDS: float = Field(default=30.0, gt=0, le=300)
    AGENT_MAX_STEPS: int = Field(default=6, ge=1, le=20)


settings = Settings()
"""Shared application settings instance."""
