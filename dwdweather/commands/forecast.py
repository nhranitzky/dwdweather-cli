from __future__ import annotations

from datetime import timedelta
from typing import Annotated

import typer

from dwdweather.api import brightsky_get
from dwdweather.errors import DwdWeatherError
from dwdweather.render import echo_json, echo_toon, render_forecast_daily, render_forecast_hourly
from dwdweather.weather import aggregate_daily, utc_hour_now

from .common import (
    LocationArgument,
    OutputFormat,
    OutputOption,
    handle_error,
    meta,
    resolve_location,
    resolve_output,
    resolve_tz,
)


def forecast(
    location: LocationArgument,
    days: Annotated[int, typer.Option("--days", min=1, max=10, help="Number of forecast days.")] = 3,
    daily: Annotated[bool, typer.Option("--daily", help="Show daily aggregate rows.")] = False,
    tz: Annotated[str | None, typer.Option("--tz", envvar="DWDWEATHER_TZ", help="Timezone for timestamps.")] = None,
    output: OutputOption = None,
) -> None:
    """Show hourly or daily weather forecast for LOCATION."""
    output = resolve_output(output)
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
            raise DwdWeatherError(
                "NO_DATA",
                "No forecast data available for this location.",
                4,
                suggestion="Check the location and date range, or list nearby stations with `dwdweather stations`.",
            )
        source = ((data or {}).get("sources") or [{}])[0]
        mode = "daily" if daily else "hourly"
        payload_records = aggregate_daily(records) if daily else records
        if output in (OutputFormat.json, OutputFormat.toon):
            payload = {
                "meta": meta("forecast", mode, timezone),
                "location": place,
                "data": {"source": source, "records": payload_records},
            }
            if output == OutputFormat.toon:
                echo_toon(payload)
            else:
                echo_json(payload)
            return
        if daily:
            render_forecast_daily(place["short_name"], payload_records, source)
        else:
            render_forecast_hourly(place["short_name"], records, source, days)
    except DwdWeatherError as exc:
        handle_error(exc, output)
