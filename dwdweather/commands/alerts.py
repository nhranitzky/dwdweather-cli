from __future__ import annotations

from typing import Any

from dwdweather.api import brightsky_get
from dwdweather.errors import DwdWeatherError
from dwdweather.render import echo_json, echo_toon, render_alerts

from .common import LocationArgument, OutputFormat, OutputOption, handle_error, meta, resolve_location, resolve_output

SEVERITY_RANK = {
    "extreme": 4,
    "severe": 3,
    "moderate": 2,
    "minor": 1,
}


def alerts(
    location: LocationArgument,
    output: OutputOption = None,
) -> None:
    """Show active DWD weather warnings for LOCATION."""
    output = resolve_output(output)
    try:
        place = resolve_location(location)
        data = brightsky_get("/alerts", {"lat": place["lat"], "lon": place["lon"]})
        alert_list = sort_alerts((data or {}).get("alerts", []))
        location_info = (data or {}).get("location") or {}
        municipality = location_info.get("name") or place["short_name"]
        warn_cell = location_info.get("warn_cell_id") or ""
        if output in (OutputFormat.json, OutputFormat.toon):
            payload = {
                "meta": meta("alerts", "alerts"),
                "location": place,
                "data": {
                    "municipality": municipality,
                    "warn_cell_id": warn_cell,
                    "alerts": alert_list,
                },
            }
            if output == OutputFormat.toon:
                echo_toon(payload)
            else:
                echo_json(payload)
            return
        render_alerts(municipality, warn_cell, alert_list)
    except DwdWeatherError as exc:
        handle_error(exc, output)


def sort_alerts(alerts_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        alerts_data,
        key=lambda item: (-SEVERITY_RANK.get(str(item.get("severity") or "").lower(), 0), item.get("onset") or ""),
    )
