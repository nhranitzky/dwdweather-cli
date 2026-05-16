from __future__ import annotations

from datetime import timedelta
from typing import Annotated, Any

import typer
from rich.table import Table

from dwdweather.api import brightsky_get
from dwdweather.errors import DwdWeatherError
from dwdweather.render import (
    add_hourly_row,
    console,
    echo_json,
    fmt_precip,
    fmt_sunshine,
    fmt_temp,
    fmt_wind,
    make_hourly_table,
)
from dwdweather.weather import aggregate_daily, utc_hour_now

from .common import LocationArgument, OutputFormat, OutputOption, handle_error, meta, resolve_location, resolve_tz


def forecast(
    location: LocationArgument,
    days: Annotated[int, typer.Option("--days", "-d", min=1, max=10, help="Number of forecast days.")] = 3,
    daily: Annotated[bool, typer.Option("--daily", help="Show daily aggregate rows.")] = False,
    tz: Annotated[str | None, typer.Option("--tz", envvar="DWDWEATHER_TZ", help="Timezone for timestamps.")] = None,
    output: OutputOption = OutputFormat.text,
) -> None:
    """Show hourly or daily weather forecast for LOCATION."""
    timezone = resolve_tz(tz)
    try:
        place = resolve_location(location)
        start = utc_hour_now()
        end = start + timedelta(days=days)
        data = brightsky_get(
            "/weather",
            {
                "lat": place["lat"],
                "lon": place["lon"],
                "date": start.strftime("%Y-%m-%dT%H:%M"),
                "last_date": end.strftime("%Y-%m-%dT%H:%M"),
                "tz": timezone,
            },
        )
        records = (data or {}).get("weather", [])
        if not records:
            raise DwdWeatherError("NO_DATA", "No forecast data available for this location.", 4)
        source = ((data or {}).get("sources") or [{}])[0]
        mode = "daily" if daily else "hourly"
        payload_records = aggregate_daily(records) if daily else records
        if output == OutputFormat.json:
            echo_json(
                {
                    "meta": meta("forecast", mode, timezone),
                    "location": place,
                    "data": {"source": source, "records": payload_records},
                }
            )
            return
        if daily:
            _render_daily(place["short_name"], payload_records, source)
        else:
            _render_hourly(place["short_name"], records, source, days)
    except DwdWeatherError as exc:
        handle_error(exc, output)


def _render_hourly(label: str, records: list[dict[str, Any]], source: dict[str, Any], days: int) -> None:
    table = make_hourly_table(f"Hourly Forecast - {label}")
    for record in records:
        add_hourly_row(table, record)
    station = source.get("station_name") or "MOSMIX forecast"
    console.print(table)
    console.print(f"[dim]{station} | {len(records)} hourly records for {days} day(s)[/]")


def _render_daily(label: str, rows: list[dict[str, Any]], source: dict[str, Any]) -> None:
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
