from __future__ import annotations

from typing import Annotated, Any

import typer
from rich.table import Table

from dwdweather.api import brightsky_get
from dwdweather.errors import DwdWeatherError
from dwdweather.render import console, echo_json, fmt_timestamp

from .common import LocationArgument, OutputFormat, OutputOption, handle_error, meta, resolve_location


def stations(
    location: LocationArgument,
    radius: Annotated[int, typer.Option("--radius", "-r", min=1, max=1000, help="Search radius in kilometres.")] = 50,
    limit: Annotated[int, typer.Option("--limit", "-n", min=1, max=100, help="Maximum number of stations.")] = 15,
    output: OutputOption = OutputFormat.text,
) -> None:
    """List DWD observation stations near LOCATION."""
    try:
        place = resolve_location(location)
        data = brightsky_get("/sources", {"lat": place["lat"], "lon": place["lon"], "max_dist": radius * 1000})
        sources = sorted((data or {}).get("sources", []), key=lambda item: item.get("distance") or 0)[:limit]
        if not sources:
            raise DwdWeatherError("NO_DATA", f"No DWD stations found within {radius} km of {place['short_name']}.", 4)
        if output == OutputFormat.json:
            echo_json(
                {
                    "meta": meta("stations", "stations"),
                    "location": place,
                    "data": {
                        "radius_km": radius,
                        "limit": limit,
                        "stations": sources,
                    },
                }
            )
            return
        _render_text(place["short_name"], radius, sources)
    except DwdWeatherError as exc:
        handle_error(exc, output)


def _render_text(label: str, radius: int, sources: list[dict[str, Any]]) -> None:
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
