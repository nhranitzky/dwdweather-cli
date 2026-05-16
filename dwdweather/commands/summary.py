from __future__ import annotations

from datetime import timedelta
from typing import Annotated, Any

import typer
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from dwdweather.api import brightsky_get
from dwdweather.errors import DwdWeatherError
from dwdweather.render import (
    console,
    echo_json,
    fmt_humidity,
    fmt_precip,
    fmt_pressure,
    fmt_sunshine,
    fmt_temp,
    fmt_timestamp,
    fmt_visibility,
    fmt_wind,
    weather_icon,
)
from dwdweather.weather import aggregate_daily, utc_hour_now

from .alerts import sort_alerts
from .common import LocationArgument, OutputFormat, OutputOption, handle_error, meta, resolve_location, resolve_tz


def summary(
    location: LocationArgument,
    days: Annotated[int, typer.Option("--days", "-d", min=1, max=10, help="Number of forecast days.")] = 5,
    tz: Annotated[str | None, typer.Option("--tz", envvar="DWDWEATHER_TZ", help="Timezone for timestamps.")] = None,
    output: OutputOption = OutputFormat.text,
) -> None:
    """Show current weather, daily outlook, and active alerts."""
    timezone = resolve_tz(tz)
    try:
        place = resolve_location(location)
        current_data = brightsky_get("/current_weather", {"lat": place["lat"], "lon": place["lon"], "tz": timezone})
        current_weather = (current_data or {}).get("weather") or (current_data or {}).get("current_weather") or {}
        current_source = ((current_data or {}).get("sources") or [{}])[0]
        if not current_weather:
            raise DwdWeatherError("NO_DATA", "No current weather data available for this location.", 4)

        start = utc_hour_now()
        end = start + timedelta(days=days)
        forecast_data = brightsky_get(
            "/weather",
            {
                "lat": place["lat"],
                "lon": place["lon"],
                "date": start.strftime("%Y-%m-%dT%H:%M"),
                "last_date": end.strftime("%Y-%m-%dT%H:%M"),
                "tz": timezone,
            },
        )
        records = (forecast_data or {}).get("weather", [])
        if not records:
            raise DwdWeatherError("NO_DATA", "No forecast data available for this location.", 4)
        forecast_rows = aggregate_daily(records)

        alert_data = brightsky_get("/alerts", {"lat": place["lat"], "lon": place["lon"]}, optional=True)
        alert_list = sort_alerts((alert_data or {}).get("alerts", [])) if alert_data else []

        if output == OutputFormat.json:
            echo_json(
                {
                    "meta": meta("summary", "summary", timezone),
                    "location": place,
                    "data": {
                        "current": current_weather,
                        "current_source": current_source,
                        "forecast": forecast_rows,
                        "alerts": alert_list,
                    },
                }
            )
            return
        _render_text(place["short_name"], current_weather, current_source, forecast_rows, alert_list, days)
    except DwdWeatherError as exc:
        handle_error(exc, output)


def _render_text(
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
