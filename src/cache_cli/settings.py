import argparse
from collections.abc import Sequence
from typing import Self

from pydantic import Field, HttpUrl, PositiveFloat, PositiveInt, model_validator
from pydantic_settings import BaseSettings, CliApp, CliSettingsSource, SettingsConfigDict

STDIO = "-"


class CliSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CACHE_CLI_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        cli_prog_name="cache-cli",
        cli_kebab_case=True,
        cli_hide_none_type=True,
        # Not AliasChoices: validation aliases bypass env_prefix, so plain HOST or R would leak in.
        cli_shortcuts={
            "host": "h",
            "repeat": "r",
            "input": "i",
            "json-data": ["j", "json"],
            "output": "o",
        },
    )

    host: HttpUrl = Field(
        default=HttpUrl("http://localhost:8000"), description="base URL of the cache service"
    )
    repeat: PositiveInt = Field(default=1, description="number of create + read iterations")
    input: str | None = Field(default=None, description="JSON input file, or - for stdin")
    json_data: str | None = Field(default=None, description="JSON input passed inline")
    output: str = Field(default=STDIO, description="output file, or - for stdout")
    timeout_seconds: PositiveFloat = Field(default=30.0, description="timeout of each request")

    @model_validator(mode="after")
    def _exactly_one_input_source(self) -> Self:
        if (self.input is None) == (self.json_data is None):
            raise ValueError("pass exactly one of --input or --json")
        return self


def parse_settings(argv: Sequence[str]) -> CliSettings:
    # The spec uses -h for --host, so argparse's built-in -h/--help becomes --help only.
    parser = argparse.ArgumentParser(
        prog="cache-cli",
        description="Create a payload on the cache service and read it back.",
        add_help=False,
        allow_abbrev=False,
    )
    parser.add_argument("--help", action="help", help="show this help message and exit")
    source = CliSettingsSource[argparse.ArgumentParser](CliSettings, root_parser=parser)
    return CliApp.run(CliSettings, cli_args=list(argv), cli_settings_source=source)
