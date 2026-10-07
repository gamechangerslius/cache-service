import json
import sys
import time
from collections.abc import Sequence
from contextlib import ExitStack
from pathlib import Path
from typing import NoReturn, TextIO

import httpx
from pydantic import ValidationError

from cache_cli.settings import STDIO, CliSettings, parse_settings
from cache_service.schemas import PayloadCreate, PayloadCreated, PayloadRead

EXIT_OK = 0
EXIT_SERVICE_ERROR = 1
EXIT_USAGE_ERROR = 2


class ServiceError(Exception):
    pass


def main(argv: Sequence[str] | None = None) -> NoReturn:
    try:
        settings = parse_settings(sys.argv[1:] if argv is None else argv)
    except ValidationError as exc:
        _report(_describe(exc), sys.stderr)
        sys.exit(EXIT_USAGE_ERROR)
    with httpx.Client(base_url=str(settings.host), timeout=settings.timeout_seconds) as client:
        sys.exit(run(settings, client, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr))


def run(
    settings: CliSettings, client: httpx.Client, *, stdin: TextIO, stdout: TextIO, stderr: TextIO
) -> int:
    with ExitStack() as stack:
        try:
            payload = PayloadCreate.model_validate_json(_read_input(settings, stdin))
            out = (
                stdout
                if settings.output == STDIO
                else stack.enter_context(Path(settings.output).open("w", encoding="utf-8"))
            )
        except ValidationError as exc:
            _report(f"invalid input: {_describe(exc)}", stderr)
            return EXIT_USAGE_ERROR
        except OSError as exc:
            _report(str(exc), stderr)
            return EXIT_USAGE_ERROR

        for iteration in range(1, settings.repeat + 1):
            try:
                record = _run_iteration(client, payload, iteration)
            except (httpx.HTTPError, ServiceError) as exc:
                _report(str(exc), stderr)
                return EXIT_SERVICE_ERROR
            except ValidationError as exc:
                _report(f"unexpected response: {_describe(exc)}", stderr)
                return EXIT_SERVICE_ERROR
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            out.flush()
    return EXIT_OK


def _read_input(settings: CliSettings, stdin: TextIO) -> str:
    if settings.json_data is not None:
        return settings.json_data
    if settings.input is None or settings.input == STDIO:
        return stdin.read()
    return Path(settings.input).read_text(encoding="utf-8")


def _run_iteration(
    client: httpx.Client, payload: PayloadCreate, iteration: int
) -> dict[str, object]:
    started = time.perf_counter()
    create_response = _checked(client.post("/payload", json=payload.model_dump()))
    created = PayloadCreated.model_validate_json(create_response.content)
    read_response = _checked(client.get(f"/payload/{created.id}"))
    read = PayloadRead.model_validate_json(read_response.content)
    return {
        "iteration": iteration,
        "id": str(created.id),
        "created": create_response.status_code == httpx.codes.CREATED,
        "output": read.output,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
    }


def _checked(response: httpx.Response) -> httpx.Response:
    if response.is_error:
        request = response.request
        raise ServiceError(
            f"{request.method} {request.url} returned {response.status_code}: {response.text}"
        )
    return response


def _describe(error: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(map(str, detail['loc']))}: {detail['msg']}" if detail["loc"] else detail["msg"]
        for detail in error.errors()
    )


def _report(message: str, stderr: TextIO) -> None:
    print(f"cache-cli: {message}", file=stderr)
