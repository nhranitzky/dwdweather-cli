from __future__ import annotations

from datetime import datetime, time
from typing import Annotated, Any

import typer
from rich.table import Table

from dwdweather.api import brightsky_get
from dwdweather.errors import DwdWeatherError
from dwdweather.render import (
    add_hourly_row,
    console,
    echo_json,
    fmt_humidity,
    fmt_precip,
    fmt_sunshine,
    fmt_temp,
    fmt_wind,
    make_hourly_table,
)
from dwdweather.weather import aggregate_daily

from .common import (
    LocationArgument,
    OutputFormat,
    OutputOption,
    handle_error,
    meta,
    parse_date,
    resolve_location,
    resolve_tz,
)


def history(
    location: LocationArgument,
    date_value: Annotated[str, typer.Option("--date", "-d", help="Start date, YYYY-MM-DD.")],
    end_date: Annotated[str | None, typer.Option("--end-date", "-e", help="Inclusive end date, YYYY-MM-DD.")] = None,
    daily: Annotated[bool, typer.Option("--daily", help="Show daily aggregate rows.")] = False,
    tz: Annotated[str | None, typer.Option("--tz", envvar="DWDWEATHER_TZ", help="Timezone for timestamps.")] = None,
    output: OutputOption = OutputFormat.text,
) -> None:
    """Query historical weather observations for LOCATION."""
    timezone = resolve_tz(tz)
    start_date = parse_date(date_value, "--date")
    final_date = parse_date(end_date, "--end-date") if end_date else start_date
    if final_date < start_date:
        raise typer.BadParameter("--end-date must be greater than or equal to --date.")
    if (final_date - start_date).days + 1 > 366:
        raise typer.BadParameter("history date ranges may not exceed 366 days.")

    try:
        place = resolve_location(location)
        start = datetime.combine(start_date, time.min)
        end = datetime.combine(final_date, time(hour=23, minute=59))
        data = brightsky_get(
            "/weather",
            {
                "lat": place["lat"],
                "lon": place["lon"],
                "date": start.strftime("%Y-%m-%d"),
                "last_date": end.strftime("%Y-%m-%dT%H:%M"),
                "tz": timezone,
            },
        )
        records = (data or {}).get("weather", [])
        if not records:
            raise DwdWeatherError("NO_DATA", "No historical data available for this location and date range.", 4)
        sources = (data or {}).get("sources") or []
        mode = "daily" if daily else "hourly"
        payload_records = aggregate_daily(records) if daily else records
        period = date_value if not end_date else f"{date_value} to {end_date}"
        if output == OutputFormat.json:
            echo_json(
                {
                    "meta": meta("history", mode, timezone),
                    "location": place,
                    "data": {
                        "period": period,
                        "sources": sources,
                        "records": payload_records,
                    },
                }
            )
            return
        if daily:
            _render_daily(place["short_name"], period, payload_records, sources)
        else:
            _render_hourly(place["short_name"], period, records, sources)
    except DwdWeatherError as exc:
        handle_error(exc, output)


def _render_hourly(label: str, period: str, records: list[dict[str, Any]], sources: list[dict[str, Any]]) -> None:
    table = make_hourly_table(f"Historical Weather - {label} [{period}]")
    for record in records:
        add_hourly_row(table, record)
    console.print(table)
    console.print(f"[dim]{_source_footer(sources)} | {len(records)} records[/]")


def _render_daily(label: str, period: str, rows: list[dict[str, Any]], sources: list[dict[str, Any]]) -> None:
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


def _source_footer(sources: list[dict[str, Any]]) -> str:
    stations = sorted({source.get("station_name") or "?" for source in sources})
    observation_types = sorted({source.get("observation_type") or "?" for source in sources})
    return f"Stations: {', '.join(stations)} | Observation types: {', '.join(observation_types)}"
