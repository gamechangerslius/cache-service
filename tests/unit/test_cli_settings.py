from pathlib import Path

import pytest
from pydantic import ValidationError

from cache_cli.settings import STDIO, parse_settings


@pytest.fixture(autouse=True)
def _run_in_empty_directory(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)


def test_defaults() -> None:
    settings = parse_settings(["-i", "-"])

    assert str(settings.host) == "http://localhost:8000/"
    assert settings.repeat == 1
    assert settings.input == STDIO
    assert settings.output == STDIO


def test_short_flags_match_long_flags() -> None:
    short = parse_settings(["-h", "http://svc:9000", "-r", "3", "-i", "in.json", "-o", "out"])
    long = parse_settings(
        ["--host", "http://svc:9000", "--repeat", "3", "--input", "in.json", "--output", "out"]
    )

    assert short == long
    assert str(short.host) == "http://svc:9000/"
    assert (short.repeat, short.input, short.output) == (3, "in.json", "out")


@pytest.mark.parametrize("flag", ["-j", "--json", "--json-data"])
def test_inline_json_flags(flag: str) -> None:
    assert parse_settings([flag, '{"list_1": []}']).json_data == '{"list_1": []}'


@pytest.mark.parametrize(
    "argv",
    [
        pytest.param(["-r", "0", "-i", "-"], id="repeat-zero"),
        pytest.param(["-r", "many", "-i", "-"], id="repeat-not-a-number"),
        pytest.param(["-h", "not a url", "-i", "-"], id="invalid-host"),
        pytest.param(["-i", "-", "-j", "{}"], id="both-input-sources"),
        pytest.param([], id="no-input-source"),
    ],
)
def test_rejects_invalid_arguments(argv: list[str]) -> None:
    with pytest.raises(ValidationError):
        parse_settings(argv)


def test_rejects_abbreviated_flags() -> None:
    with pytest.raises(SystemExit) as exit_info:
        parse_settings(["--js", "{}"])

    assert exit_info.value.code == 2


def test_help_uses_long_flag_and_keeps_h_for_host(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        parse_settings(["--help"])

    help_text = capsys.readouterr().out
    assert exit_info.value.code == 0
    assert "-h HttpUrl" in help_text
    assert "--help" in help_text


def test_reads_defaults_from_env_file(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text(
        "CACHE_CLI_HOST=http://from-dotenv:8000\n"
        "CACHE_CLI_REPEAT=4\n"
        "CACHE_SERVICE_LOG_LEVEL=DEBUG\n"
    )

    settings = parse_settings(["-i", "-"])

    assert str(settings.host) == "http://from-dotenv:8000/"
    assert settings.repeat == 4


def test_flags_beat_environment_which_beats_env_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".env").write_text("CACHE_CLI_HOST=http://from-dotenv:1\nCACHE_CLI_REPEAT=4\n")
    monkeypatch.setenv("CACHE_CLI_HOST", "http://from-environment:2")

    from_environment = parse_settings(["-i", "-"])
    from_flag = parse_settings(["-i", "-", "-h", "http://from-flag:3"])

    assert str(from_environment.host) == "http://from-environment:2/"
    assert from_environment.repeat == 4
    assert str(from_flag.host) == "http://from-flag:3/"


def test_ignores_unprefixed_environment_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOST", "http://leaked:1")
    monkeypatch.setenv("R", "9")

    settings = parse_settings(["-i", "-"])

    assert str(settings.host) == "http://localhost:8000/"
    assert settings.repeat == 1
