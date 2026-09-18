from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime configuration. Values come from environment variables / .env.

    Never hardcode secrets here — this class only defines *how* to read them.
    """

    telegram_bot_token: str
    allowed_telegram_user_id: int | None = None

    gemini_api_key: str
    gemini_model: str = "gemini-2.5-flash"

    database_url: str = "sqlite+aiosqlite:///./data/interview_trainer.db"

    default_interval_minutes: int = 15

    log_level: str = "INFO"

    # Set by Render (and most free web-service hosts) automatically; only
    # matters when running as a Web Service rather than a plain worker.
    port: int | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
