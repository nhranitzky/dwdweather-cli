from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from . import toon as _toon

console = Console()
error_console = Console(stderr=True)


def echo_json(payload: dict[str, Any]) -> None:
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))


def echo_toon(payload: dict[str, Any]) -> None:
    typer.echo("```toon\n" + _toon.dumps(payload) + "```")


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

SEVERITY_COLORS = {
    "minor": "yellow",
    "moderate": "dark_orange",
    "severe": "red",
    "extreme": "bold red",
}

SEVERITY_ICONS = {
    "minor": "⚠️",
    "moderate": "🟠",
    "severe": "🔴",
    "extreme": "🆘",
}


def render_current(label: str, weather: dict[str, Any], source: dict[str, Any]) -> None:
    table = Table(show_header=False, padding=(0, 2))
    table.add_column("Field", style="bold cyan", no_wrap=True)
    table.add_column("Value")
    rows = [
        ("Observed at", fmt_timestamp(weather.get("timestamp"))),
        ("Temperature", fmt_temp(weather.get("temperature"))),
        ("Dew point", fmt_temp(weather.get("dew_point"))),
        ("Relative humidity", fmt_humidity(weather.get("relative_humidity"))),
        ("Wind", fmt_wind(weather.get("wind_speed"), weather.get("wind_direction"))),
        ("Gusts", fmt_wind(weather.get("wind_gust_speed"), weather.get("wind_gust_direction"))),
        ("Recent precipitation", fmt_precip(weather.get("precipitation_10"))),
        ("Cloud cover", f"{weather.get('cloud_cover')} %" if weather.get("cloud_cover") is not None else "-"),
        ("Pressure", fmt_pressure(weather.get("pressure_msl"))),
        ("Visibility", fmt_visibility(weather.get("visibility"))),
        ("Sunshine", fmt_sunshine(weather.get("sunshine_30"))),
    ]
    for field, value in rows:
        table.add_row(field, value)

    condition = str(weather.get("condition") or "").replace("_", " ").title()
    station = source.get("station_name") or "unknown station"
    distance = source.get("distance")
    footer = f"Station: {station}"
    if distance is not None:
        footer += f" ({distance / 1000:.1f} km away)"
    console.print(
        Panel(
            table,
            title=f"[bold green]Current Weather[/] - {weather_icon(weather)} {condition} - {label}",
            subtitle=f"[dim]{footer}[/]",
            expand=False,
        )
    )


def render_forecast_hourly(label: str, records: list[dict[str, Any]], source: dict[str, Any], days: int) -> None:
    table = make_hourly_table(f"Hourly Forecast - {label}")
    for record in records:
        add_hourly_row(table, record)
    station = source.get("station_name") or "MOSMIX forecast"
    console.print(table)
    console.print(f"[dim]{station} | {len(records)} hourly records for {days} day(s)[/]")


def render_forecast_daily(label: str, rows: list[dict[str, Any]], source: dict[str, Any]) -> None:
    table = Table(title=f"Daily Forecast - {label}", show_header=True, header_style="bold cyan")
    table.add_column("Date", no_wrap=True)
    table.add_column("", no_wrap=True)
    table.add_column("Low", justify="right")
    table.add_column("High", justify="right")
    table.add_column("Rain", justify="right")
    table.add_column("Wind", justify="right")
    table.add_column("Sunshine", justify="right")
    for row in rows:
        table.add_row(
            row["date"],
            row["condition_icon"],
            fmt_temp(row["temperature_min"]),
            fmt_temp(row["temperature_max"]),
            fmt_precip(row["precipitation_total"]),
            fmt_wind(row["wind_speed_avg"]),
            fmt_sunshine(row["sunshine_total"]),
        )
    console.print(table)
    console.print(f"[dim]Source: {source.get('station_name') or 'MOSMIX forecast'}[/]")


def _source_footer(sources: list[dict[str, Any]]) -> str:
    stations = sorted({source.get("station_name") or "?" for source in sources})
    observation_types = sorted({source.get("observation_type") or "?" for source in sources})
    return f"Stations: {', '.join(stations)} | Observation types: {', '.join(observation_types)}"


def render_history_hourly(
    label: str, period: str, records: list[dict[str, Any]], sources: list[dict[str, Any]], *, truncated: bool = False
) -> None:
    table = make_hourly_table(f"Historical Weather - {label} [{period}]")
    for record in records:
        add_hourly_row(table, record)
    console.print(table)
    console.print(f"[dim]{_source_footer(sources)} | {len(records)} records[/]")
    if truncated:
        console.print("[yellow]Result truncated by --limit; use a larger --limit to see more records.[/]")


def render_history_daily(
    label: str, period: str, rows: list[dict[str, Any]], sources: list[dict[str, Any]], *, truncated: bool = False
) -> None:
    table = Table(title=f"Historical Daily Summary - {label} [{period}]", show_header=True, header_style="bold cyan")
    table.add_column("Date", no_wrap=True)
    table.add_column("Low", justify="right")
    table.add_column("High", justify="right")
    table.add_column("Avg", justify="right")
    table.add_column("Rain", justify="right")
    table.add_column("Wind", justify="right")
    table.add_column("Avg RH", justify="right")
    table.add_column("Sunshine", justify="right")
    for row in rows:
        table.add_row(
            row["date"],
            fmt_temp(row["temperature_min"]),
            fmt_temp(row["temperature_max"]),
            fmt_temp(row["temperature_avg"]),
            fmt_precip(row["precipitation_total"]),
            fmt_wind(row["wind_speed_avg"]),
            fmt_humidity(row["relative_humidity_avg"]),
            fmt_sunshine(row["sunshine_total"]),
        )
    console.print(table)
    console.print(f"[dim]{_source_footer(sources)}[/]")
    if truncated:
        console.print("[yellow]Result truncated by --limit; use a larger --limit to see more records.[/]")


def render_stations(label: str, radius: int, sources: list[dict[str, Any]]) -> None:
    table = Table(title=f"DWD Stations near {label} (radius: {radius} km)", show_header=True, header_style="bold cyan")
    table.add_column("#", justify="right", style="dim")
    table.add_column("Station", no_wrap=True)
    table.add_column("DWD ID", style="dim")
    table.add_column("Type", no_wrap=True)
    table.add_column("Dist (km)", justify="right")
    table.add_column("Height (m)", justify="right")
    table.add_column("First Record", no_wrap=True)
    table.add_column("Last Record", no_wrap=True)
    for index, source in enumerate(sources, 1):
        table.add_row(
            str(index),
            source.get("station_name") or "?",
            source.get("dwd_station_id") or "?",
            str(source.get("observation_type") or "?").replace("_", " "),
            f"{(source.get('distance') or 0) / 1000:.1f}",
            str(source.get("height") or "?"),
            fmt_timestamp(source.get("first_record"), fmt="%Y-%m-%d"),
            fmt_timestamp(source.get("last_record"), fmt="%Y-%m-%d"),
        )
    console.print(table)
    console.print(f"[dim]{len(sources)} station(s) shown[/]")


def render_summary(
    label: str,
    current_weather: dict[str, Any],
    current_source: dict[str, Any],
    forecast_rows: list[dict[str, Any]],
    alert_list: list[dict[str, Any]],
    days: int,
) -> None:
    if alert_list:
        worst = alert_list[0]
        headline = worst.get("headline") or worst.get("event") or "Weather alert"
        suffix = f" (+{len(alert_list) - 1} more)" if len(alert_list) > 1 else ""
        console.print(Panel(Text.from_markup(f"[bold red]{headline}[/]{suffix}"), border_style="red", expand=False))

    current_text = Text()
    condition = str(current_weather.get("condition") or "").replace("_", " ").title()
    current_text.append(
        f"{weather_icon(current_weather)} {fmt_temp(current_weather.get('temperature'))} {condition}\n\n", style="bold"
    )
    current_text.append(f"Wind: {fmt_wind(current_weather.get('wind_speed'), current_weather.get('wind_direction'))}\n")
    current_text.append(f"Humidity: {fmt_humidity(current_weather.get('relative_humidity'))}\n")
    current_text.append(f"Pressure: {fmt_pressure(current_weather.get('pressure_msl'))}\n")
    current_text.append(f"Visibility: {fmt_visibility(current_weather.get('visibility'))}\n")
    current_text.append(
        f"\nObserved {fmt_timestamp(current_weather.get('timestamp'))} - {current_source.get('station_name') or '?'}",
        style="dim",
    )
    console.print(Panel(current_text, title=f"[bold green]Now[/] - {label}", expand=False))

    table = Table(title=f"{days}-Day Outlook", show_header=True, header_style="bold cyan")
    table.add_column("Date", no_wrap=True)
    table.add_column("", no_wrap=True)
    table.add_column("Low", justify="right")
    table.add_column("High", justify="right")
    table.add_column("Rain", justify="right")
    table.add_column("Wind", justify="right")
    table.add_column("Sunshine", justify="right")
    for row in forecast_rows:
        table.add_row(
            row["date"],
            row["condition_icon"],
            fmt_temp(row["temperature_min"]),
            fmt_temp(row["temperature_max"]),
            fmt_precip(row["precipitation_total"]),
            fmt_wind(row["wind_speed_avg"]),
            fmt_sunshine(row["sunshine_total"]),
        )
    console.print(table)


def render_alerts(municipality: str, warn_cell: str, alert_list: list[dict[str, Any]]) -> None:
    console.print(f"[bold]Weather Alerts[/] - {municipality}" + (f" [dim]({warn_cell})[/]" if warn_cell else ""))
    if not warn_cell:
        console.print("[dim]DWD alerts are only available for locations within Germany.[/]")
    if not alert_list:
        console.print("[bold green]No active weather warnings.[/]")
        return

    for alert in alert_list:
        severity = str(alert.get("severity") or "unknown").lower()
        color = SEVERITY_COLORS.get(severity, "yellow")
        icon = SEVERITY_ICONS.get(severity, "⚠️")
        headline = alert.get("headline") or alert.get("event") or "Weather alert"
        body = Text()
        description = alert.get("description") or ""
        instruction = alert.get("instruction") or ""
        if description:
            body.append(f"{description}\n")
        if instruction:
            body.append(f"\n{instruction}\n", style="italic")
        body.append(
            f"\nFrom: {fmt_timestamp(alert.get('onset'))}  Until: {fmt_timestamp(alert.get('expires'))}",
            style="dim",
        )
        console.print(
            Panel(body, title=f"{icon} [{color}]{str(headline).upper()}[/]", border_style=color, expand=False)
        )


def _flag_summary(param: dict[str, Any]) -> str:
    flag = str(param["flags"][0])
    if param["type"] == "choice":
        return f"{flag} [{'|'.join(param.get('choices', []))}]"
    if param["type"] == "boolean":
        return flag
    return f"{flag} {param['type'].upper()}"


def render_commands(commands: list[dict[str, Any]]) -> None:
    table = Table(title="Available Commands", show_header=True, header_style="bold cyan")
    table.add_column("Command", style="bold", no_wrap=True)
    table.add_column("Help")
    table.add_column("Arguments", no_wrap=True)
    table.add_column("Options")
    for command in commands:
        arguments = ", ".join(
            f"{arg['name'].upper()}..." if arg["variadic"] else arg["name"].upper() for arg in command["arguments"]
        )
        options = ", ".join(_flag_summary(option) for option in command["options"])
        table.add_row(command["name"], command["help"], arguments, options)
    console.print(table)
    console.print(f"[dim]{len(commands)} command(s). Use --output json for full option details.[/]")
