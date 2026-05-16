from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

console = Console()
error_console = Console(stderr=True)


def echo_json(payload: dict[str, Any]) -> None:
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))


def generated_at() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def fmt_timestamp(ts: str | None, fmt: str = "%a %d.%m. %H:%M %z") -> str:
    if not ts:
        return "-"
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.strftime(fmt)


def fmt_temp(value: float | None) -> str:
    return "-" if value is None else f"{value:.1f} °C"


def fmt_wind(speed: float | None, direction: int | None = None) -> str:
    if speed is None:
        return "-"
    result = f"{speed:.1f} km/h"
    if direction is not None:
        result += f"  {_compass(direction)}"
    return result


def fmt_precip(value: float | None) -> str:
    return "-" if value is None else f"{value:.1f} mm"


def fmt_humidity(value: float | None) -> str:
    return "-" if value is None else f"{value:.0f} %"


def fmt_pressure(value: float | None) -> str:
    return "-" if value is None else f"{value:.1f} hPa"


def fmt_visibility(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value / 1000:.1f} km" if value >= 1000 else f"{value:.0f} m"


def fmt_sunshine(value: float | None) -> str:
    return "-" if value is None else f"{value:.0f} min"


def weather_icon(record: dict[str, Any]) -> str:
    icon = record.get("icon") or ""
    condition = record.get("condition") or ""
    return ICON_MAP.get(icon) or CONDITION_ICONS.get(condition, "🌡️")


def make_hourly_table(title: str) -> Table:
    table = Table(title=title, show_header=True, header_style="bold cyan")
    table.add_column("Time", style="dim", no_wrap=True)
    table.add_column("", no_wrap=True)
    table.add_column("Temp", justify="right")
    table.add_column("Precip", justify="right")
    table.add_column("Wind", justify="right")
    table.add_column("RH", justify="right")
    table.add_column("Pressure", justify="right")
    table.add_column("Visibility", justify="right")
    table.add_column("Sunshine", justify="right")
    return table


def add_hourly_row(table: Table, record: dict[str, Any]) -> None:
    table.add_row(
        fmt_timestamp(record.get("timestamp")),
        weather_icon(record),
        fmt_temp(record.get("temperature")),
        fmt_precip(record.get("precipitation")),
        fmt_wind(record.get("wind_speed"), record.get("wind_direction")),
        fmt_humidity(record.get("relative_humidity")),
        fmt_pressure(record.get("pressure_msl")),
        fmt_visibility(record.get("visibility")),
        fmt_sunshine(record.get("sunshine")),
    )


def _compass(degrees: int) -> str:
    directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    index = round(degrees / 45) % 8
    return directions[index]


CONDITION_ICONS = {
    "dry": "☀️",
    "fog": "🌫️",
    "rain": "🌧️",
    "sleet": "🌨️",
    "snow": "❄️",
    "hail": "🌩️",
    "thunderstorm": "⛈️",
    "null": "❓",
}

ICON_MAP = {
    "clear-day": "☀️",
    "clear-night": "🌙",
    "partly-cloudy-day": "⛅",
    "partly-cloudy-night": "🌛",
    "cloudy": "☁️",
    "fog": "🌫️",
    "wind": "🌬️",
    "rain": "🌧️",
    "sleet": "🌨️",
    "snow": "❄️",
    "hail": "🌩️",
    "thunderstorm": "⛈️",
}
