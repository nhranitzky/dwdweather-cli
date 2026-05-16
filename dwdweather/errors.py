from __future__ import annotations

import json
import traceback
from dataclasses import dataclass
from typing import NoReturn

import typer

from .render import error_console


@dataclass
class DwdWeatherError(Exception):
    code: str
    message: str
    exit_code: int = 1
    details: str | None = None


def json_error_payload(error: DwdWeatherError) -> str:
    return json.dumps(
        {
            "error": {
                "code": error.code,
                "message": error.message,
                "exit_code": error.exit_code,
            }
        },
        ensure_ascii=False,
        indent=2,
    )


def raise_for_error(error: DwdWeatherError, *, output: str, debug: bool) -> NoReturn:
    if output == "json":
        typer.echo(json_error_payload(error))
        if debug:
            if error.details:
                error_console.print(f"[dim]{error.details}[/]")
            traceback.print_exception(error)
    else:
        error_console.print(f"[bold red]{error.code}:[/] {error.message}")
        if debug and error.details:
            error_console.print(f"[dim]{error.details}[/]")
    raise typer.Exit(error.exit_code)
