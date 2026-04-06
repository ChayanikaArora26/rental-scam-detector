"""
config.py — Centralised settings via pydantic-settings.
All values read from environment variables / .env file.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── Database ─────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://rentalguard:rentalguard_dev@localhost:5432/rentalguard"

    # ── JWT ──────────────────────────────────────────────────────
    JWT_SECRET: str = "change-me-in-production-use-32-chars-min"
    JWT_REFRESH_SECRET: str = "change-me-refresh-secret-32-chars-min"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_EXPIRE_DAYS: int = 7

    # ── OAuth2 Google (optional) ──────────────────────────────────
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/auth/google/callback"

    # ── SMTP ─────────────────────────────────────────────────────
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASS: str = ""
    SMTP_FROM: str = "noreply@rentalguard.app"

    # ── App ──────────────────────────────────────────────────────
    APP_URL: str = "http://localhost:3000"
    API_URL: str = "http://localhost:8000"

    # ── Anthropic ────────────────────────────────────────────────
    ANTHROPIC_API_KEY: str = ""

    # ── Security ─────────────────────────────────────────────────
    BCRYPT_ROUNDS: int = 12
    RATE_LIMIT_LOGIN: str = "5/10minutes"   # max attempts per window
    ACCOUNT_LOCKOUT_MINUTES: int = 30
    MAX_FAILED_ATTEMPTS: int = 5


@lru_cache
def get_settings() -> Settings:
    return Settings()
