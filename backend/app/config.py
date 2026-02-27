"""
Centralised configuration — all secrets come from environment variables.
Copy .env.example → .env and fill in your values.
"""
from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    ENV: str = "development"

    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql://autodev:autodev@localhost:5432/autodev"

    # ── Redis / Celery ────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # ── LLM ───────────────────────────────────────────────────────────────────
    ANTHROPIC_API_KEY: str = ""
    LLM_MODEL: str = "claude-opus-4-6"          # swap to claude-sonnet-4-6 for speed
    LLM_MAX_TOKENS: int = 4096
    LLM_TEMPERATURE: float = 0.1                 # low temp = deterministic refactors
    LLM_MAX_RETRIES: int = 3
    LLM_TIMEOUT_SECONDS: int = 60

    # ── GitHub ────────────────────────────────────────────────────────────────
    GITHUB_TOKEN: str = ""
    GITHUB_PR_BASE_BRANCH: str = "main"

    # ── Analysis thresholds ───────────────────────────────────────────────────
    MAX_CYCLOMATIC_COMPLEXITY: int = 10
    MAX_FUNCTION_LINES: int = 50
    MAX_NESTING_DEPTH: int = 3
    MAX_PARAMETERS: int = 6
    MAX_FILE_SIZE_CHANGE_PCT: float = 0.30      # reject refactors >30 % size delta

    # ── Repo storage ─────────────────────────────────────────────────────────
    REPOS_BASE_PATH: str = "/tmp/autodev_repos"

    # ── CORS ──────────────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]

    # ── Logging ───────────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"   # "json" | "console"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
