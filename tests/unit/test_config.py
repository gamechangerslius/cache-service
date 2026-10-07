"""Settings resolution: environment beats .env, and a shared .env with CLI keys is accepted."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from cache_service.config import Settings


@pytest.fixture
def env_file(tmp_path: Path) -> Path:
    path = tmp_path / ".env"
    path.write_text(
        "CACHE_SERVICE_LOG_LEVEL=DEBUG\n"
        "CACHE_SERVICE_TRANSFORMER_MAX_CONCURRENCY=3\n"
        "CACHE_CLI_HOST=http://example.test\n"
    )
    return path


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("CACHE_SERVICE_LOG_LEVEL", "CACHE_SERVICE_TRANSFORMER_MAX_CONCURRENCY"):
        monkeypatch.delenv(key, raising=False)


def test_reads_prefixed_keys_from_env_file_and_ignores_cli_keys(env_file: Path) -> None:
    settings = Settings(_env_file=env_file)

    assert settings.log_level == "DEBUG"
    assert settings.transformer_max_concurrency == 3


def test_environment_overrides_env_file(env_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CACHE_SERVICE_LOG_LEVEL", "WARNING")

    assert Settings(_env_file=env_file).log_level == "WARNING"


def test_unprefixed_variables_are_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    assert Settings(_env_file=None).log_level == "INFO"


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("CACHE_SERVICE_TRANSFORMER_MAX_CONCURRENCY", "0"),
        ("CACHE_SERVICE_TRANSFORMER_LATENCY_SECONDS", "-1"),
        ("CACHE_SERVICE_LOG_LEVEL", "VERBOSE"),
    ],
)
def test_rejects_invalid_values(monkeypatch: pytest.MonkeyPatch, key: str, value: str) -> None:
    monkeypatch.setenv(key, value)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)
