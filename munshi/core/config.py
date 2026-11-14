"""Runtime settings. Everything configurable comes from env vars (see .env.example)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = f"sqlite:///{REPO_ROOT / 'munshi.db'}"
    JWT_SECRET: str = "dev-only-change-me-dev-only-change-me"
    JWT_TTL_MINUTES: int = 12 * 60

    # AI: "mock" (default) or "prune". There is no direct-provider fallback.
    LLM_MODE: str = "mock"
    PRUNE_BASE_URL: str = "https://prune.invalid"
    PRUNE_API_KEY: str = ""
    PRUNE_MODEL: str = "prune-default"
    PRUNE_TIMEOUT_S: float = 30.0
    # PRUNE_MODE is read by aintegration.build_gateway; "mock" forces PruneMock even when key is set.
    PRUNE_MODE: str = "live"

    # Anchoring: "hardhat" (falls back to mock if node unreachable) or "mock".
    ANCHOR_MODE: str = "hardhat"
    CHAIN_RPC_URL: str = "http://127.0.0.1:8545"
    ANCHOR_PRIVATE_KEY: str = ""  # empty -> use first unlocked Hardhat account
    DEPLOYMENT_FILE: str = str(REPO_ROOT / "chain" / "deployments" / "local.json")

    CONFIDENCE_THRESHOLD: float = 0.85
    AUTO_DRAFT_AMOUNT_LIMIT_PAISE: int = 10_000_000  # Rs 1,00,000

    PUBLIC_BASE_URL: str = "http://localhost:8000"
    CORS_ORIGINS: str = "*"
    EXPORT_OPENAPI: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
