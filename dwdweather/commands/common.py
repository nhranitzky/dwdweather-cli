from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import typer

from dwdweather.config import runtime
from dwdweather.errors import DwdWeatherError, raise_for_error
from dwdweather.geocode import Location, geocode_location
from dwdweather.render import generated_at


class OutputFormat(StrEnum):
    text = "text"
    json = "json"


LocationArgument = Annotated[
    list[str],
    typer.Argument(help="Location name in Germany. Multi-word locations may be passed unquoted."),
]

OutputOption = Annotated[
    OutputFormat,
    typer.Option("--output", case_sensitive=False, help="Output format."),
]


def resolve_location(tokens: list[str]) -> Location:
    query = " ".join(tokens).strip()
    if not query:
        raise typer.BadParameter("LOCATION is required.")
    return geocode_location(query)


def resolve_tz(value: str | None) -> str:
    tz = value or "Europe/Berlin"
    try:
        ZoneInfo(tz)
    except ZoneInfoNotFoundError as exc:
        raise typer.BadParameter(f"Invalid timezone: {tz}") from exc
    return tz


def meta(command: str, mode: str, timezone: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "command": command,
        "mode": mode,
        "generated_at": generated_at(),
    }
    if timezone is not None:
        payload["timezone"] = timezone
    return payload


def handle_error(error: DwdWeatherError, output: OutputFormat) -> None:
    raise_for_error(error, output=output.value, debug=runtime.debug)


def parse_date(value: str, option_name: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise typer.BadParameter(f"{option_name} must use YYYY-MM-DD.") from exc
