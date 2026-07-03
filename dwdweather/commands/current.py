from __future__ import annotations

from typing import Annotated

import typer

from dwdweather.api import brightsky_get
from dwdweather.errors import DwdWeatherError
from dwdweather.render import echo_json, echo_toon, render_current

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


def current(
    location: LocationArgument,
    tz: Annotated[str | None, typer.Option("--tz", envvar="DWDWEATHER_TZ", help="Timezone for timestamps.")] = None,
    output: OutputOption = None,
) -> None:
    """Show current weather for LOCATION."""
    output = resolve_output(output)
    timezone = resolve_tz(tz)
    try:
        place = resolve_location(location)
        data = brightsky_get("/current_weather", {"lat": place["lat"], "lon": place["lon"], "tz": timezone})
        if data is None:
            raise DwdWeatherError(
                "NO_DATA",
                "No current weather data available for this location.",
                4,
                suggestion="Check the location and date range, or list nearby stations with `dwdweather stations`.",
            )
        weather = data.get("weather") or data.get("current_weather") or {}
        source = (data.get("sources") or [{}])[0]
        if not weather:
            raise DwdWeatherError(
                "NO_DATA",
                "No current weather data available for this location.",
                4,
                suggestion="Check the location and date range, or list nearby stations with `dwdweather stations`.",
            )
        if output in (OutputFormat.json, OutputFormat.toon):
            payload = {
                "meta": meta("current", "current", timezone),
                "location": place,
                "data": {"weather": weather, "source": source},
            }
            if output == OutputFormat.toon:
                echo_toon(payload)
            else:
                echo_json(payload)
            return
        render_current(place["short_name"], weather, source)
    except DwdWeatherError as exc:
        handle_error(exc, output)
