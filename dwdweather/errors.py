from __future__ import annotations

import json
import traceback
from dataclasses import dataclass
from typing import NoReturn

import typer

from . import toon as _toon
from .render import error_console


@dataclass
class DwdWeatherError(Exception):
    code: str
    message: str
    exit_code: int = 1
    details: str | None = None
    suggestion: str | None = None


def _error_payload(error: DwdWeatherError) -> dict[str, str | int]:
    payload: dict[str, str | int] = {
        "code": error.code,
        "message": error.message,
        "exit_code": error.exit_code,
    }
    if error.suggestion is not None:
        payload["suggestion"] = error.suggestion
    return payload


def json_error_payload(error: DwdWeatherError) -> str:
    return json.dumps(
        {"error": _error_payload(error)},
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
    elif output == "toon":
        typer.echo("```toon\n" + _toon.dumps({"error": _error_payload(error)}) + "```")
        if debug:
            if error.details:
                error_console.print(f"[dim]{error.details}[/]")
            traceback.print_exception(error)
    else:
        error_console.print(f"[bold red]{error.code}:[/] {error.message}")
        if debug and error.details:
            error_console.print(f"[dim]{error.details}[/]")
    raise typer.Exit(error.exit_code)
