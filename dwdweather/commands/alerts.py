from __future__ import annotations

from typing import Any

from rich.panel import Panel
from rich.text import Text

from dwdweather.api import brightsky_get
from dwdweather.errors import DwdWeatherError
from dwdweather.render import console, echo_json, fmt_timestamp

from .common import LocationArgument, OutputFormat, OutputOption, handle_error, meta, resolve_location

SEVERITY_RANK = {
    "extreme": 4,
    "severe": 3,
    "moderate": 2,
    "minor": 1,
}

SEVERITY_COLORS = {
    "minor": "yellow",
    "moderate": "dark_orange",
    "severe": "red",
    "extreme": "bold red",
}

SEVERITY_ICONS = {
    "minor": "⚠️",
    "moderate": "🟠",
    "severe": "🔴",
    "extreme": "🆘",
}


def alerts(
    location: LocationArgument,
    output: OutputOption = OutputFormat.text,
) -> None:
    """Show active DWD weather warnings for LOCATION."""
    try:
        place = resolve_location(location)
        data = brightsky_get("/alerts", {"lat": place["lat"], "lon": place["lon"]})
        alert_list = sort_alerts((data or {}).get("alerts", []))
        location_info = (data or {}).get("location") or {}
        municipality = location_info.get("name") or place["short_name"]
        warn_cell = location_info.get("warn_cell_id") or ""
        if output == OutputFormat.json:
            echo_json(
                {
                    "meta": meta("alerts", "alerts"),
                    "location": place,
                    "data": {
                        "municipality": municipality,
                        "warn_cell_id": warn_cell,
                        "alerts": alert_list,
                    },
                }
            )
            return
        _render_text(municipality, warn_cell, alert_list)
    except DwdWeatherError as exc:
        handle_error(exc, output)


def sort_alerts(alerts_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        alerts_data,
        key=lambda item: (-SEVERITY_RANK.get(str(item.get("severity") or "").lower(), 0), item.get("onset") or ""),
    )


def _render_text(municipality: str, warn_cell: str, alert_list: list[dict[str, Any]]) -> None:
    console.print(f"[bold]Weather Alerts[/] - {municipality}" + (f" [dim]({warn_cell})[/]" if warn_cell else ""))
    if not warn_cell:
        console.print("[dim]DWD alerts are only available for locations within Germany.[/]")
    if not alert_list:
        console.print("[bold green]No active weather warnings.[/]")
        return

    for alert in alert_list:
        severity = str(alert.get("severity") or "unknown").lower()
        color = SEVERITY_COLORS.get(severity, "yellow")
        icon = SEVERITY_ICONS.get(severity, "⚠️")
        headline = alert.get("headline") or alert.get("event") or "Weather alert"
        body = Text()
        description = alert.get("description") or ""
        instruction = alert.get("instruction") or ""
        if description:
            body.append(f"{description}\n")
        if instruction:
            body.append(f"\n{instruction}\n", style="italic")
        body.append(
            f"\nFrom: {fmt_timestamp(alert.get('onset'))}  Until: {fmt_timestamp(alert.get('expires'))}",
            style="dim",
        )
        console.print(
            Panel(body, title=f"{icon} [{color}]{str(headline).upper()}[/]", border_style=color, expand=False)
        )
