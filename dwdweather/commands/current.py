from __future__ import annotations

from typing import Annotated, Any

import typer
from rich.panel import Panel
from rich.table import Table

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

from .common import LocationArgument, OutputFormat, OutputOption, handle_error, meta, resolve_location, resolve_tz


def current(
    location: LocationArgument,
    tz: Annotated[str | None, typer.Option("--tz", envvar="DWDWEATHER_TZ", help="Timezone for timestamps.")] = None,
    output: OutputOption = OutputFormat.text,
) -> None:
    """Show current weather for LOCATION."""
    timezone = resolve_tz(tz)
    try:
        place = resolve_location(location)
        data = brightsky_get("/current_weather", {"lat": place["lat"], "lon": place["lon"], "tz": timezone})
        if data is None:
            raise DwdWeatherError("NO_DATA", "No current weather data available for this location.", 4)
        weather = data.get("weather") or data.get("current_weather") or {}
        source = (data.get("sources") or [{}])[0]
        if not weather:
            raise DwdWeatherError("NO_DATA", "No current weather data available for this location.", 4)
        if output == OutputFormat.json:
            echo_json(
                {
                    "meta": meta("current", "current", timezone),
                    "location": place,
                    "data": {"weather": weather, "source": source},
                }
            )
            return
        _render_text(place["short_name"], weather, source)
    except DwdWeatherError as exc:
        handle_error(exc, output)


def _render_text(label: str, weather: dict[str, Any], source: dict[str, Any]) -> None:
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
