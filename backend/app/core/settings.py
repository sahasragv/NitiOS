"""Application configuration loaded from environment variables."""

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


_BACKEND_DIRECTORY = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime settings for the Setu backend application.

    Values are loaded from process environment variables and, when present, the
    ``backend/.env`` file. Environment variables take precedence over file values.
    """

    model_config = SettingsConfigDict(
        env_file=_BACKEND_DIRECTORY / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "Setu"
    APP_ENV: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = Field(default=8000, ge=1, le=65535)
    LOG_LEVEL: str = "INFO"
    LLM_PROVIDER: Literal["ollama", "anthropic", "gemini"] = "ollama"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_DEFAULT_MODEL: str = "qwen2.5:3b"
    OLLAMA_TIMEOUT_SECONDS: float = Field(default=300.0, gt=0, le=1800)
    ANTHROPIC_API_KEY: SecretStr | None = None
    ANTHROPIC_MODEL: str = "claude-sonnet-5-5"
    ANTHROPIC_BASE_URL: str = "https://api.anthropic.com"
    ANTHROPIC_MAX_TOKENS: int = Field(default=4096, ge=1, le=64000)
    ANTHROPIC_TIMEOUT_SECONDS: float = Field(default=120.0, gt=0, le=600)
    GEMINI_API_KEY: SecretStr | None = None
    GEMINI_MODEL: str = "gemini-3-flash-preview"
    GEMINI_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta/openai"
    GEMINI_REASONING_EFFORT: Literal["", "minimal", "low", "medium", "high"] = "low"
    GEMINI_TIMEOUT_SECONDS: float = Field(default=120.0, gt=0, le=600)
    DATABASE_URL: str = f"sqlite+aiosqlite:///{(_BACKEND_DIRECTORY / 'setu.db').as_posix()}"
    SECRET_KEY: SecretStr | None = None
    """Encrypts stored account tokens; changing it disconnects every connected account."""
    PUBLIC_URL: str = "http://localhost:5173"
    """Where the browser reaches Setu; OAuth callbacks and post-login redirects are built from it."""
    SESSION_TTL_DAYS: int = Field(default=30, ge=1, le=365)
    ALLOWED_EMAILS: list[str] = []
    """When non-empty, only these Google accounts may sign in."""
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: SecretStr | None = None
    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: SecretStr | None = None
    GITHUB_OAUTH_SCOPES: str = "read:user repo"
    MCP_CONFIG_PATH: Path = _BACKEND_DIRECTORY / "mcp_servers.json"
    MCP_TIMEOUT_SECONDS: float = Field(default=30.0, gt=0, le=300)
    AGENT_MAX_STEPS: int = Field(default=6, ge=1, le=20)
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]


settings = Settings()
"""Shared application settings instance."""
