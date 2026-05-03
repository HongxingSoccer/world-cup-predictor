"""Application settings loaded from environment variables.

Uses pydantic-settings so values can come from a real environment, a `.env`
file at the project root, or both. Import the singleton `settings` everywhere;
do not re-instantiate `Settings()` in application code.
"""
from __future__ import annotations

from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Storage ---
    DATABASE_URL: str = Field(
        default="postgresql+psycopg2://wcp:wcp@localhost:5432/wcp",
        description="SQLAlchemy database URL.",
    )
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis URL used as the Celery broker / cache.",
    )

    # --- Streaming ---
    KAFKA_BROKERS: List[str] = Field(
        default_factory=lambda: ["localhost:9092"],
        description="Comma-separated Kafka bootstrap servers.",
    )

    # --- External APIs ---
    API_FOOTBALL_KEY: Optional[str] = None
    ODDS_API_KEY: Optional[str] = None

    # --- Scraping ---
    PROXY_POOL_URL: Optional[str] = None
    SCRAPER_CONCURRENT: int = Field(default=8, ge=1, le=128)

    # --- Logging ---
    LOG_LEVEL: str = "INFO"

    # --- Ingest scope ---
    # List of "{league_id}:{year}" tokens consumed by ApiFootballAdapter / Celery
    # match-sync tasks. Override via env (comma-separated) when adding qualifiers
    # or club leagues in addition to the default World Cup 2026 entry.
    ACTIVE_COMPETITIONS: List[str] = Field(
        default_factory=lambda: ["1:2026"],
    )

    # --- ML inference API (Phase 2) ---
    # Static API key validated by the FastAPI middleware on every request.
    # Empty string disables auth (useful for local dev / tests).
    API_KEY: str = Field(default="")
    # Per-IP request budget enforced by the middleware. 100 req/min ≈ 1.67 req/s.
    API_RATE_LIMIT_PER_MIN: int = Field(default=100, ge=1)
    # Comma-separated CORS origins. '*' = allow all (development only).
    API_CORS_ORIGINS: List[str] = Field(default_factory=lambda: ["*"])
    # Cache TTL for /predictions/today (seconds).
    PREDICTIONS_TODAY_CACHE_TTL: int = Field(default=300, ge=0)

    # --- Phase 5 productisation ---
    # Static admin token guarding the /admin/* API. Empty disables the routes
    # entirely — set a real value (≥ 32 chars) in staging/production.
    ADMIN_API_TOKEN: str = Field(default="")
    # In-process cache TTL for feature-flag values; matches design §4.4.2 (30s).
    FEATURE_FLAGS_REFRESH_SECONDS: int = Field(default=30, ge=1)

    # --- MLflow (Phase 2) ---
    MLFLOW_TRACKING_URI: str = Field(
        default="http://localhost:5000",
        description="MLflow tracking server endpoint.",
    )
    MLFLOW_DEFAULT_EXPERIMENT: str = Field(default="wcp-poisson-baseline")

    # --- S3 / MinIO (Phase 3 — share-card object storage) ---
    # Endpoint can be a MinIO URL (e.g. http://minio:9000) or any S3-API-
    # compatible target. Empty string disables uploads — `CardGenerator`
    # then logs and skips remote storage so local dev keeps working.
    S3_ENDPOINT: str = Field(default="http://localhost:9000")
    S3_ACCESS_KEY: str = Field(default="wcp-minio")
    S3_SECRET_KEY: str = Field(default="wcp-minio-secret")
    S3_REGION: str = Field(default="us-east-1")
    S3_BUCKET_CARDS: str = Field(default="wcp-cards")
    # Public-facing URL prefix used in `share_cards.image_url`. Typically a
    # CDN sitting in front of MinIO/S3. Empty falls back to `S3_ENDPOINT`.
    S3_PUBLIC_BASE_URL: str = Field(default="")

    @field_validator(
        "KAFKA_BROKERS", "ACTIVE_COMPETITIONS", "API_CORS_ORIGINS", mode="before"
    )
    @classmethod
    def _split_csv(cls, value):
        # Accept comma-separated strings from env files for any List[str] field.
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("LOG_LEVEL")
    @classmethod
    def _normalize_log_level(cls, value: str) -> str:
        return value.upper()


settings = Settings()
