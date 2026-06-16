"""Application configuration loaded from environment variables.

Settings are read from the process environment (and, for local non-Docker
development, from a `.env` file). When running via Docker Compose the variables
are injected from the project-root `.env` through `env_file`.
"""

from __future__ import annotations

import json
from functools import lru_cache

from pydantic import computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # --- Application ---
    APP_NAME: str = "Expensitor API"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # --- Security ---
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14
    ALGORITHM: str = "HS256"

    # --- PostgreSQL ---
    POSTGRES_SERVER: str = "db"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "expensitor"
    POSTGRES_PASSWORD: str = "expensitor"
    POSTGRES_DB: str = "expensitor"

    # --- Connection pool ---
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # --- CORS ---
    BACKEND_CORS_ORIGINS: list[str] = []

    # --- Domain defaults ---
    DEFAULT_BASE_CURRENCY: str = "INR"

    # --- Exchange-rate provider ---
    FRANKFURTER_BASE_URL: str = "https://api.frankfurter.app"

    # --- Optional Ollama narrator (C5 Phase 3b) ---
    # Disabled by default: the app is fully functional on the deterministic
    # commentary alone. Ollama may ONLY rephrase already-computed narration;
    # it never calculates, decides, or changes any financial fact. Local only.
    OLLAMA_ENABLED: bool = False
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1:8b-instruct-q4_K_M"
    OLLAMA_TIMEOUT_SECONDS: float = 2.0
    OLLAMA_NARRATION_STYLE: str = "balanced"  # concise | balanced | detailed

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def _assemble_cors_origins(cls, value: object) -> list[str]:
        """Accept a JSON array, a comma-separated string, or a real list."""
        if value is None or value == "":
            return []
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("["):
                return list(json.loads(stripped))
            return [item.strip() for item in stripped.split(",") if item.strip()]
        if isinstance(value, list):
            return value
        raise ValueError("BACKEND_CORS_ORIGINS must be a list, JSON array, or CSV string")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def DATABASE_URL(self) -> str:
        """Async SQLAlchemy URL (asyncpg driver), used by the app and Alembic."""
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
