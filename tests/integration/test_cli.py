import io
import json
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

from cache_cli.main import EXIT_OK, EXIT_USAGE_ERROR, run
from cache_cli.settings import CliSettings
from cache_service.config import Settings
from cache_service.main import create_app
from tests.support import SpyTransformer, live_server

SAMPLE_JSON = json.dumps(
    {
        "list_1": ["first string", "second string", "third string"],
        "list_2": ["other string", "another string", "last string"],
    }
)
SAMPLE_OUTPUT = (
    "FIRST STRING, OTHER STRING, SECOND STRING, ANOTHER STRING, THIRD STRING, LAST STRING"
)


@pytest.fixture
def service(settings: Settings, spy: SpyTransformer) -> Iterator[httpx.Client]:
    with (
        live_server(create_app(settings, transformer=spy)) as url,
        httpx.Client(base_url=url) as client,
    ):
        yield client


def run_cli(
    service: httpx.Client, settings: CliSettings, stdin: str = ""
) -> tuple[int, list[dict[str, object]], str]:
    stdout, stderr = io.StringIO(), io.StringIO()
    code = run(settings, service, stdin=io.StringIO(stdin), stdout=stdout, stderr=stderr)
    records = [json.loads(line) for line in stdout.getvalue().splitlines()]
    return code, records, stderr.getvalue()


def test_repeat_reuses_the_payload_and_reports_each_iteration(
    service: httpx.Client, spy: SpyTransformer
) -> None:
    code, records, stderr = run_cli(
        service, CliSettings(_env_file=None, json_data=SAMPLE_JSON, repeat=3)
    )

    assert (code, stderr) == (EXIT_OK, "")
    assert [record["iteration"] for record in records] == [1, 2, 3]
    assert [record["created"] for record in records] == [True, False, False]
    assert len({record["id"] for record in records}) == 1
    assert {record["output"] for record in records} == {SAMPLE_OUTPUT}
    assert spy.calls.total() == 6


def test_reads_input_from_stdin(service: httpx.Client) -> None:
    code, records, _ = run_cli(service, CliSettings(_env_file=None, input="-"), SAMPLE_JSON)

    assert code == EXIT_OK
    assert records[0]["output"] == SAMPLE_OUTPUT


def test_reads_input_file_and_writes_output_file(service: httpx.Client, tmp_path: Path) -> None:
    input_file, output_file = tmp_path / "input.json", tmp_path / "output.jsonl"
    input_file.write_text(SAMPLE_JSON)

    code, records, _ = run_cli(
        service,
        CliSettings(_env_file=None, input=str(input_file), output=str(output_file), repeat=2),
    )

    assert code == EXIT_OK
    assert records == []
    assert len(output_file.read_text().splitlines()) == 2


@pytest.mark.parametrize(
    "json_data",
    [
        pytest.param('{"list_1": ["a"], "list_2": []}', id="unequal-lengths"),
        pytest.param("not json", id="malformed-json"),
    ],
)
def test_invalid_input_never_reaches_the_service(
    service: httpx.Client, spy: SpyTransformer, json_data: str
) -> None:
    code, records, stderr = run_cli(service, CliSettings(_env_file=None, json_data=json_data))

    assert code == EXIT_USAGE_ERROR
    assert records == []
    assert stderr.startswith("cache-cli: invalid input:")
    assert not spy.calls


def test_missing_input_file_is_reported(service: httpx.Client, tmp_path: Path) -> None:
    code, _, stderr = run_cli(
        service, CliSettings(_env_file=None, input=str(tmp_path / "missing.json"))
    )

    assert code == EXIT_USAGE_ERROR
    assert "No such file" in stderr
