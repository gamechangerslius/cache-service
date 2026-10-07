from typing import Literal

from pydantic import NonNegativeFloat, PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CACHE_SERVICE_",
        env_file=".env",
        env_file_encoding="utf-8",
        # The shared .env also holds CACHE_CLI_* keys; forbidding extras would crash startup.
        extra="ignore",
    )

    database_url: str = "sqlite+aiosqlite:///./data/cache.db"
    transformer_latency_seconds: NonNegativeFloat = 0.5
    transformer_max_concurrency: PositiveInt = 10
    log_level: LogLevel = "INFO"
