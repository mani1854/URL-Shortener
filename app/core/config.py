"""
core/config.py

Single source of truth for every configurable value.
Pydantic-settings reads from environment variables (and .env files).
All values are validated and type-coerced at startup.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ────────────────────────────────────────────────────────────
    APP_NAME: str = "URL Shortener"
    APP_VERSION: str = "1.0.0"
    APP_ENV: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = False
    SECRET_KEY: str = Field(
        "dev-secret-key-must-be-at-least-32-chars-long!", min_length=32
    )
    BASE_URL: AnyHttpUrl = "http://localhost:8000"

    # ── API ────────────────────────────────────────────────────────────────────
    API_V1_PREFIX: str = "/api/v1"
    DOCS_URL: str | None = "/docs"
    REDOC_URL: str | None = "/redoc"

    # ── Short URL ──────────────────────────────────────────────────────────────
    SHORT_CODE_LENGTH: int = Field(7, ge=4, le=20)
    MAX_CUSTOM_ALIAS_LENGTH: int = Field(50, ge=4, le=100)

    # ── PostgreSQL ─────────────────────────────────────────────────────────────
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "url_shortener"
    DATABASE_URL: str | None = None

    # Pool settings
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30

    # ── Redis ──────────────────────────────────────────────────────────────────
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = ""
    REDIS_URL: str | None = None
    CACHE_TTL_SECONDS: int = 1800  # 30 minutes default TTL

    # ── Rate limiting ──────────────────────────────────────────────────────────
    RATE_LIMIT_ANON_REQUESTS: int = 50      # 50 requests / hour for anonymous users
    RATE_LIMIT_AUTH_REQUESTS: int = 500    # 500 requests / hour for authenticated users
    RATE_LIMIT_WINDOW_SECONDS: int = 3600  # 1 hour window (in seconds)
    RATE_LIMIT_REQUESTS: int = 50          # legacy fallback

    # ── CORS ───────────────────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] | str = ["*"]
    CORS_ALLOW_CREDENTIALS: bool = True

    # ── JWT / Auth ─────────────────────────────────────────────────────────────
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(15, ge=1)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(7, ge=1)

    # ── Logging ────────────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: Literal["json", "console"] = "json"

    # ── Validators ─────────────────────────────────────────────────────────────
    @field_validator("CORS_ORIGINS", mode="after")
    @classmethod
    def parse_cors_origins(cls, v: list[str] | str) -> list[str]:
        if isinstance(v, str):
            if v.strip() == "*":
                return ["*"]
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_database_url(cls, v: str | None, info) -> str:
        if v:
            return v
        data = info.data
        return (
            f"postgresql+asyncpg://{data['POSTGRES_USER']}:{data['POSTGRES_PASSWORD']}"
            f"@{data['POSTGRES_SERVER']}:{data['POSTGRES_PORT']}/{data['POSTGRES_DB']}"
        )

    @field_validator("REDIS_URL", mode="before")
    @classmethod
    def assemble_redis_url(cls, v: str | None, info) -> str:
        if v:
            return v
        data = info.data
        auth = f":{data['REDIS_PASSWORD']}@" if data.get("REDIS_PASSWORD") else ""
        return f"redis://{auth}{data['REDIS_HOST']}:{data['REDIS_PORT']}/{data['REDIS_DB']}"

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton – safe to call repeatedly."""
    return Settings()


# Module-level singleton for direct imports
settings: Settings = get_settings()
