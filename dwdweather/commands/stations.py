from __future__ import annotations

from typing import Annotated

import typer

from dwdweather.api import brightsky_get
from dwdweather.errors import DwdWeatherError
from dwdweather.render import echo_json, echo_toon, render_stations

from .common import LocationArgument, OutputFormat, OutputOption, handle_error, meta, resolve_location, resolve_output


def stations(
    location: LocationArgument,
    radius: Annotated[int, typer.Option("--radius", min=1, max=1000, help="Search radius in kilometres.")] = 50,
    limit: Annotated[int, typer.Option("--limit", min=1, max=100, help="Maximum number of stations.")] = 15,
    output: OutputOption = None,
) -> None:
    """List DWD observation stations near LOCATION."""
    output = resolve_output(output)
    try:
        place = resolve_location(location)
        data = brightsky_get("/sources", {"lat": place["lat"], "lon": place["lon"], "max_dist": radius * 1000})
        sources = sorted((data or {}).get("sources", []), key=lambda item: item.get("distance") or 0)[:limit]
        if not sources:
            raise DwdWeatherError(
                "NO_DATA",
                f"No DWD stations found within {radius} km of {place['short_name']}.",
                4,
                suggestion="Increase --radius to search a wider area.",
            )
        if output in (OutputFormat.json, OutputFormat.toon):
            payload = {
                "meta": meta("stations", "stations"),
                "location": place,
                "data": {
                    "radius_km": radius,
                    "limit": limit,
                    "stations": sources,
                },
            }
            if output == OutputFormat.toon:
                echo_toon(payload)
            else:
                echo_json(payload)
            return
        render_stations(place["short_name"], radius, sources)
    except DwdWeatherError as exc:
        handle_error(exc, output)
