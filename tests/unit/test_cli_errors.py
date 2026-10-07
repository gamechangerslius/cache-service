import io
import json
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from cache_cli.main import EXIT_SERVICE_ERROR, EXIT_USAGE_ERROR, main, run
from cache_cli.settings import CliSettings

SAMPLE_JSON = json.dumps({"list_1": ["a"], "list_2": ["b"]})


def run_against(handler: Callable[[httpx.Request], httpx.Response]) -> tuple[int, str]:
    stderr = io.StringIO()
    with httpx.Client(transport=httpx.MockTransport(handler), base_url="http://test") as client:
        code = run(
            CliSettings(_env_file=None, json_data=SAMPLE_JSON),
            client,
            stdin=io.StringIO(),
            stdout=io.StringIO(),
            stderr=stderr,
        )
    return code, stderr.getvalue()


def test_reports_service_errors_with_status_and_body() -> None:
    code, stderr = run_against(
        lambda _: httpx.Response(502, json={"detail": "Transformer service failed"})
    )

    assert code == EXIT_SERVICE_ERROR
    assert "returned 502" in stderr
    assert "Transformer service failed" in stderr


def test_reports_connection_errors() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    code, stderr = run_against(refuse)

    assert code == EXIT_SERVICE_ERROR
    assert "connection refused" in stderr


def test_reports_unexpected_responses() -> None:
    code, stderr = run_against(lambda _: httpx.Response(201, json={"unexpected": True}))

    assert code == EXIT_SERVICE_ERROR
    assert "unexpected response" in stderr


def test_main_rejects_invalid_arguments(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as exit_info:
        main(["-r", "0", "-j", SAMPLE_JSON])

    assert exit_info.value.code == EXIT_USAGE_ERROR
    assert "repeat: Input should be greater than 0" in capsys.readouterr().err


def test_main_reports_an_unreachable_service(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as exit_info:
        main(["-h", "http://127.0.0.1:1", "-j", SAMPLE_JSON])

    assert exit_info.value.code == EXIT_SERVICE_ERROR
    assert capsys.readouterr().err.startswith("cache-cli: ")
