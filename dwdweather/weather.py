from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from .render import weather_icon


def utc_hour_now() -> datetime:
    return datetime.now(UTC).replace(minute=0, second=0, microsecond=0)


def aggregate_daily(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    days: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        timestamp = record.get("timestamp")
        if timestamp:
            days[str(timestamp)[:10]].append(record)

    result: list[dict[str, Any]] = []
    for day, day_records in sorted(days.items()):
        temperatures = _column(day_records, "temperature")
        precipitations = _column(day_records, "precipitation")
        winds = _column(day_records, "wind_speed")
        humidities = _column(day_records, "relative_humidity")
        sunshine = _column(day_records, "sunshine")
        icons = [weather_icon(record) for record in day_records]

        result.append(
            {
                "date": day,
                "condition_icon": max(set(icons), key=icons.count) if icons else "🌡️",
                "temperature_min": min(temperatures) if temperatures else None,
                "temperature_max": max(temperatures) if temperatures else None,
                "temperature_avg": _avg(temperatures),
                "precipitation_total": sum(precipitations) if precipitations else None,
                "wind_speed_avg": _avg(winds),
                "relative_humidity_avg": _avg(humidities),
                "sunshine_total": sum(sunshine) if sunshine else None,
            }
        )
    return result


def _column(records: list[dict[str, Any]], key: str) -> list[float]:
    return [value for record in records if (value := record.get(key)) is not None]


def _avg(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None
