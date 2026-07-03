from __future__ import annotations

from datetime import datetime, time
from typing import Annotated

import typer

from dwdweather.api import brightsky_get
from dwdweather.errors import DwdWeatherError
from dwdweather.render import echo_json, echo_toon, render_history_daily, render_history_hourly
from dwdweather.weather import aggregate_daily

from .common import (
    LocationArgument,
    OutputFormat,
    OutputOption,
    handle_error,
    meta,
    parse_date,
    resolve_location,
    resolve_output,
    resolve_tz,
)

MAX_HOURLY_RECORDS = 366 * 24


def history(
    location: LocationArgument,
    date_value: Annotated[str, typer.Option("--date", help="Start date, YYYY-MM-DD.")],
    end_date: Annotated[str | None, typer.Option("--end-date", help="Inclusive end date, YYYY-MM-DD.")] = None,
    daily: Annotated[bool, typer.Option("--daily", help="Show daily aggregate rows.")] = False,
    tz: Annotated[str | None, typer.Option("--tz", envvar="DWDWEATHER_TZ", help="Timezone for timestamps.")] = None,
    limit: Annotated[
        int, typer.Option("--limit", min=1, help="Maximum number of hourly records to return.")
    ] = MAX_HOURLY_RECORDS,
    output: OutputOption = None,
) -> None:
    """Query historical weather observations for LOCATION."""
    output = resolve_output(output)
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
            raise DwdWeatherError(
                "NO_DATA",
                "No historical data available for this location and date range.",
                4,
                suggestion="Check the location and date range, or list nearby stations with `dwdweather stations`.",
            )
        sources = (data or {}).get("sources") or []
        truncated = len(records) > limit
        if truncated:
            records = records[:limit]
        mode = "daily" if daily else "hourly"
        payload_records = aggregate_daily(records) if daily else records
        period = date_value if not end_date else f"{date_value} to {end_date}"
        if output in (OutputFormat.json, OutputFormat.toon):
            payload = {
                "meta": meta("history", mode, timezone, truncated=truncated),
                "location": place,
                "data": {
                    "period": period,
                    "sources": sources,
                    "records": payload_records,
                },
            }
            if output == OutputFormat.toon:
                echo_toon(payload)
            else:
                echo_json(payload)
            return
        if daily:
            render_history_daily(place["short_name"], period, payload_records, sources, truncated=truncated)
        else:
            render_history_hourly(place["short_name"], period, records, sources, truncated=truncated)
    except DwdWeatherError as exc:
        handle_error(exc, output)
