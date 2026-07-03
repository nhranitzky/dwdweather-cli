from __future__ import annotations

import json
import traceback
from dataclasses import dataclass
from typing import Any, NoReturn

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


KNOWN_ERRORS: dict[str, dict[str, Any]] = {
    "NO_DATA": {
        "message": "No data available for this request.",
        "exit_code": 4,
        "recoverable": True,
        "suggested_action": "Check the location and date range, or list nearby stations with `dwdweather stations`.",
    },
    "LOCATION_NOT_FOUND": {
        "message": "Location not found in Germany.",
        "exit_code": 3,
        "recoverable": True,
        "suggested_action": "Check the spelling, or use a nearby larger town/city.",
    },
    "RATE_LIMITED": {
        "message": "Rate limit exceeded. Please try again later.",
        "exit_code": 1,
        "recoverable": True,
        "suggested_action": "Wait and retry; consider reducing request frequency.",
    },
    "NETWORK_ERROR": {
        "message": "Network error while contacting an upstream service.",
        "exit_code": 1,
        "recoverable": True,
        "suggested_action": "Retry; check internet connectivity.",
    },
    "SERVICE_UNAVAILABLE": {
        "message": "Upstream service is unavailable. Please try again later.",
        "exit_code": 1,
        "recoverable": True,
        "suggested_action": "Retry later.",
    },
    "API_ERROR": {
        "message": "Upstream API returned an unexpected error.",
        "exit_code": 1,
        "recoverable": False,
        "suggested_action": None,
    },
    "GEOCODING_ERROR": {
        "message": "Geocoding service returned an error.",
        "exit_code": 1,
        "recoverable": True,
        "suggested_action": "Retry later.",
    },
}

EXIT_CODES: list[dict[str, Any]] = [
    {"code": 0, "meaning": "Success"},
    {"code": 1, "meaning": "General runtime/API/network error"},
    {"code": 2, "meaning": "CLI usage or validation error"},
    {"code": 3, "meaning": "Location not found"},
    {"code": 4, "meaning": "No weather/station data for valid input"},
]


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
