from __future__ import annotations

from datetime import timedelta
from typing import Annotated

import typer

from dwdweather.api import brightsky_get
from dwdweather.errors import DwdWeatherError
from dwdweather.render import echo_json, echo_toon, render_summary
from dwdweather.weather import aggregate_daily, utc_hour_now

from .alerts import sort_alerts
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


def summary(
    location: LocationArgument,
    days: Annotated[int, typer.Option("--days", min=1, max=10, help="Number of forecast days.")] = 5,
    tz: Annotated[str | None, typer.Option("--tz", envvar="DWDWEATHER_TZ", help="Timezone for timestamps.")] = None,
    output: OutputOption = None,
) -> None:
    """Show current weather, daily outlook, and active alerts."""
    output = resolve_output(output)
    timezone = resolve_tz(tz)
    try:
        place = resolve_location(location)
        current_data = brightsky_get("/current_weather", {"lat": place["lat"], "lon": place["lon"], "tz": timezone})
        current_weather = (current_data or {}).get("weather") or (current_data or {}).get("current_weather") or {}
        current_source = ((current_data or {}).get("sources") or [{}])[0]
        if not current_weather:
            raise DwdWeatherError(
                "NO_DATA",
                "No current weather data available for this location.",
                4,
                suggestion="Check the location and date range, or list nearby stations with `dwdweather stations`.",
            )

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
            raise DwdWeatherError(
                "NO_DATA",
                "No forecast data available for this location.",
                4,
                suggestion="Check the location and date range, or list nearby stations with `dwdweather stations`.",
            )
        forecast_rows = aggregate_daily(records)

        alert_data = brightsky_get("/alerts", {"lat": place["lat"], "lon": place["lon"]}, optional=True)
        alert_list = sort_alerts((alert_data or {}).get("alerts", [])) if alert_data else []

        if output in (OutputFormat.json, OutputFormat.toon):
            payload = {
                "meta": meta("summary", "summary", timezone),
                "location": place,
                "data": {
                    "current": current_weather,
                    "current_source": current_source,
                    "forecast": forecast_rows,
                    "alerts": alert_list,
                },
            }
            if output == OutputFormat.toon:
                echo_toon(payload)
            else:
                echo_json(payload)
            return
        render_summary(place["short_name"], current_weather, current_source, forecast_rows, alert_list, days)
    except DwdWeatherError as exc:
        handle_error(exc, output)
