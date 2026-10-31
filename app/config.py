from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Social Analytics Parser"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    app_debug: bool = True

    database_url: str = "sqlite:///./analytics.db"
    sync_interval_minutes: int = 30
    seed_demo_data: bool = True

    # Optional default credentials for HTTP mode connectors.
    default_vk_token: str | None = None
    default_telegram_token: str | None = None
    default_max_token: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


BASE_DIR = Path(__file__).resolve().parent.parent
