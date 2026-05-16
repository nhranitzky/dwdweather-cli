from __future__ import annotations

import httpx

import pytest

from dwdweather.api import brightsky_get
from dwdweather.commands.alerts import sort_alerts
from dwdweather.errors import DwdWeatherError
from dwdweather.weather import aggregate_daily


def test_alert_sorting() -> None:
    alerts = [
        {"severity": "minor", "onset": "2026-05-16T12:00:00+02:00"},
        {"severity": "severe", "onset": "2026-05-16T14:00:00+02:00"},
        {"severity": "severe", "onset": "2026-05-16T13:00:00+02:00"},
    ]
    sorted_alerts = sort_alerts(alerts)
    assert [item["onset"] for item in sorted_alerts] == [
        "2026-05-16T13:00:00+02:00",
        "2026-05-16T14:00:00+02:00",
        "2026-05-16T12:00:00+02:00",
    ]


def test_aggregate_daily_schema() -> None:
    rows = aggregate_daily(
        [
            {
                "timestamp": "2026-05-16T10:00:00+02:00",
                "temperature": 10.0,
                "precipitation": 1.0,
                "wind_speed": 5.0,
                "relative_humidity": 70.0,
                "sunshine": 30.0,
                "condition": "dry",
            },
            {
                "timestamp": "2026-05-16T11:00:00+02:00",
                "temperature": 20.0,
                "precipitation": 2.0,
                "wind_speed": 15.0,
                "relative_humidity": 50.0,
                "sunshine": 60.0,
                "condition": "dry",
            },
        ]
    )
    assert rows == [
        {
            "date": "2026-05-16",
            "condition_icon": "☀️",
            "temperature_min": 10.0,
            "temperature_max": 20.0,
            "temperature_avg": 15.0,
            "precipitation_total": 3.0,
            "wind_speed_avg": 10.0,
            "relative_humidity_avg": 60.0,
            "sunshine_total": 90.0,
        }
    ]


def test_brightsky_404_maps_to_no_data(monkeypatch: pytest.MonkeyPatch) -> None:
    request = httpx.Request("GET", "https://api.brightsky.dev/weather")
    response = httpx.Response(404, request=request)

    def fake_get(*args: object, **kwargs: object) -> httpx.Response:
        raise httpx.HTTPStatusError("not found", request=request, response=response)

    monkeypatch.setattr(httpx, "get", fake_get)
    with pytest.raises(DwdWeatherError) as exc:
        brightsky_get("/weather", {})
    assert exc.value.code == "NO_DATA"
    assert exc.value.exit_code == 4
