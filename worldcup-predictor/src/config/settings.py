"""Application settings loaded from environment variables.

Uses pydantic-settings so values can come from a real environment, a `.env`
file at the project root, or both. Import the singleton `settings` everywhere;
do not re-instantiate `Settings()` in application code.
"""
from __future__ import annotations

from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from typing_extensions import Annotated


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
    KAFKA_BROKERS: Annotated[List[str], NoDecode] = Field(
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
    ACTIVE_COMPETITIONS: Annotated[List[str], NoDecode] = Field(
        default_factory=lambda: ["1:2026"],
    )

    # The Odds API sport keys to pull live fixtures + odds for. These follow the
    # Odds API naming (e.g. ``soccer_fifa_world_cup``, ``soccer_epl``); they are
    # *separate* from ACTIVE_COMPETITIONS because the two providers don't share
    # an id space. Override via env (comma-separated) when adding leagues.
    ODDS_API_SPORT_KEYS: Annotated[List[str], NoDecode] = Field(
        default_factory=lambda: ["soccer_fifa_world_cup"],
    )
    # Hard cap on Odds API calls per ingest run to protect the 500/month free
    # quota. Each sport_key listing = 1 call; per-event detail fetches are not
    # used by the bulk pipeline.
    ODDS_API_MAX_CALLS_PER_RUN: int = Field(default=10, ge=1, le=500)
    # Default competition + season used when ingesting OddsAPI fixtures whose
    # sport_title doesn't already exist as a Competition row.
    ODDS_API_DEFAULT_SEASON_YEAR: int = Field(default=2026)

    # --- ML inference API (Phase 2) ---
    # Static API key validated by the FastAPI middleware on every request.
    # Empty string disables auth (useful for local dev / tests).
    API_KEY: str = Field(default="")
    # Per-IP request budget enforced by the middleware. 100 req/min ≈ 1.67 req/s.
    API_RATE_LIMIT_PER_MIN: int = Field(default=100, ge=1)
    # Comma-separated CORS origins. '*' = allow all (development only).
    API_CORS_ORIGINS: Annotated[List[str], NoDecode] = Field(default_factory=lambda: ["*"])
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
    # Which registered model the API + Celery workers load at Production stage.
    # Switching this lets us promote a new model class (Dixon-Coles, GLM, etc.)
    # without code changes — set ACTIVE_MODEL_NAME in `.env` and restart.
    ACTIVE_MODEL_NAME: str = Field(default="poisson_v1")

    # --- LLM (Phase 4 — AI match reports) ---
    # Both keys empty → :class:`StubLLMClient` returns a templated report so
    # the report task pipeline still runs end-to-end pre-launch. Once a real
    # key is set, :func:`build_llm_client_from_settings` swaps in the real
    # provider with no other code changes.
    ANTHROPIC_API_KEY: str = Field(default="", description="Claude API key (Phase 4).")
    OPENAI_API_KEY: str = Field(default="", description="OpenAI / DeepSeek / Qwen key.")
    OPENAI_BASE_URL: str = Field(
        default="",
        description="Override OpenAI base_url for compatible providers (DeepSeek, Qwen).",
    )
    LLM_PRIMARY_MODEL: str = Field(default="claude-sonnet-4-20250514")
    LLM_FALLBACK_MODEL: str = Field(default="gpt-4o-mini")

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
        "KAFKA_BROKERS", "ACTIVE_COMPETITIONS", "ODDS_API_SPORT_KEYS", "API_CORS_ORIGINS", mode="before"
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
