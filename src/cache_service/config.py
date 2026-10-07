"""Service configuration, read from the environment and an optional ``.env`` file."""

from typing import Literal

from pydantic import NonNegativeFloat, PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Settings(BaseSettings):
    """Runtime settings of the caching service.

    Resolution order: process environment, then ``.env``, then the defaults below.
    """

    model_config = SettingsConfigDict(
        # The prefix keeps service keys apart from the CLI's (CACHE_CLI_*) in a shared .env.
        env_prefix="CACHE_SERVICE_",
        env_file=".env",
        env_file_encoding="utf-8",
        # The shared .env also holds CLI keys; validating them here would crash startup.
        extra="ignore",
    )

    database_url: str = "sqlite+aiosqlite:///./data/cache.db"
    transformer_latency_seconds: NonNegativeFloat = 0.5
    transformer_max_concurrency: PositiveInt = 10
    log_level: LogLevel = "INFO"
