from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from dwdweather.cli import app
from dwdweather.errors import DwdWeatherError

runner = CliRunner()


LOCATION = {
    "query": "Berlin",
    "name": "Berlin, Deutschland",
    "short_name": "Berlin",
    "lat": 52.52,
    "lon": 13.405,
    "source": "geocoding",
}

WEATHER_RECORD = {
    "timestamp": "2026-05-16T14:00:00+02:00",
    "condition": "dry",
    "icon": "clear-day",
    "temperature": 20.0,
    "dew_point": 10.0,
    "relative_humidity": 55.0,
    "wind_speed": 12.0,
    "wind_direction": 90,
    "wind_gust_speed": 18.0,
    "wind_gust_direction": 100,
    "precipitation": 0.0,
    "precipitation_10": 0.0,
    "cloud_cover": 10,
    "pressure_msl": 1013.2,
    "visibility": 10000,
    "sunshine": 60.0,
    "sunshine_30": 30.0,
}

SOURCE = {
    "station_name": "Berlin Station",
    "distance": 1200,
    "dwd_station_id": "001",
    "observation_type": "historical",
    "height": 50,
    "first_record": "2020-01-01T00:00:00+00:00",
    "last_record": "2026-01-01T00:00:00+00:00",
}


@pytest.fixture(autouse=True)
def clear_debug() -> None:
    from dwdweather.config import runtime

    runtime.debug = False


@pytest.fixture
def mock_location(monkeypatch: pytest.MonkeyPatch) -> None:
    from dwdweather.commands import common

    monkeypatch.setattr(common, "geocode_location", lambda query: {**LOCATION, "query": query})


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "dwdweather 1.0.0" in result.stdout


def test_bare_command_shows_help() -> None:
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "current" in result.stdout


def test_current_json_success(monkeypatch: pytest.MonkeyPatch, mock_location: None) -> None:
    from dwdweather.commands import current

    monkeypatch.setattr(
        current,
        "brightsky_get",
        lambda path, params: {"weather": WEATHER_RECORD, "sources": [SOURCE]},
    )
    result = runner.invoke(app, ["current", "Berlin", "--output", "json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["meta"]["command"] == "current"
    assert payload["meta"]["timezone"] == "Europe/Berlin"
    assert payload["location"]["query"] == "Berlin"
    assert payload["data"]["weather"]["temperature"] == 20.0


def test_forecast_daily_json_success(monkeypatch: pytest.MonkeyPatch, mock_location: None) -> None:
    from dwdweather.commands import forecast

    monkeypatch.setattr(
        forecast,
        "brightsky_get",
        lambda path, params: {"weather": [WEATHER_RECORD], "sources": [SOURCE]},
    )
    result = runner.invoke(app, ["forecast", "Berlin", "--daily", "--output", "json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["meta"]["mode"] == "daily"
    assert payload["data"]["records"][0]["temperature_min"] == 20.0
    assert "temp_min" not in payload["data"]["records"][0]


def test_history_range_validation_exits_2(mock_location: None) -> None:
    result = runner.invoke(
        app,
        ["history", "Berlin", "--date", "2024-01-01", "--end-date", "2025-01-02"],
    )
    assert result.exit_code == 2


def test_json_error_payload_on_stdout(monkeypatch: pytest.MonkeyPatch, mock_location: None) -> None:
    from dwdweather.commands import forecast

    def fail(path: str, params: dict[str, object]) -> dict[str, object]:
        raise DwdWeatherError("NO_DATA", "No forecast data available for this location.", 4)

    monkeypatch.setattr(forecast, "brightsky_get", fail)
    result = runner.invoke(app, ["forecast", "Berlin", "--output", "json"])
    assert result.exit_code == 4
    payload = json.loads(result.stdout)
    assert payload["error"]["code"] == "NO_DATA"


def test_location_not_found_exits_3(monkeypatch: pytest.MonkeyPatch) -> None:
    from dwdweather.commands import common

    def fail(query: str) -> object:
        raise DwdWeatherError("LOCATION_NOT_FOUND", "Location not found in Germany: 'Atlantis'.", 3)

    monkeypatch.setattr(common, "geocode_location", fail)
    result = runner.invoke(app, ["current", "Atlantis"])
    assert result.exit_code == 3
    assert "LOCATION_NOT_FOUND" in result.stderr


def test_timezone_env_precedence(monkeypatch: pytest.MonkeyPatch, mock_location: None) -> None:
    from dwdweather.commands import current

    seen: dict[str, str] = {}

    def fake_get(path: str, params: dict[str, str]) -> dict[str, object]:
        seen["tz"] = params["tz"]
        return {"weather": WEATHER_RECORD, "sources": [SOURCE]}

    monkeypatch.setenv("DWDWEATHER_TZ", "UTC")
    monkeypatch.setattr(current, "brightsky_get", fake_get)
    result = runner.invoke(app, ["current", "Berlin", "--output", "json"])
    assert result.exit_code == 0
    assert seen["tz"] == "UTC"


def test_stations_sort_and_limit(monkeypatch: pytest.MonkeyPatch, mock_location: None) -> None:
    from dwdweather.commands import stations

    far = {**SOURCE, "station_name": "Far", "distance": 5000}
    near = {**SOURCE, "station_name": "Near", "distance": 1000}
    monkeypatch.setattr(stations, "brightsky_get", lambda path, params: {"sources": [far, near]})
    result = runner.invoke(app, ["stations", "Berlin", "--limit", "1", "--output", "json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["data"]["stations"][0]["station_name"] == "Near"
    assert len(payload["data"]["stations"]) == 1


def test_summary_alerts_best_effort(monkeypatch: pytest.MonkeyPatch, mock_location: None) -> None:
    from dwdweather.commands import summary

    def fake_get(path: str, params: dict[str, object], optional: bool = False) -> dict[str, object] | None:
        if path == "/current_weather":
            return {"weather": WEATHER_RECORD, "sources": [SOURCE]}
        if path == "/weather":
            return {"weather": [WEATHER_RECORD], "sources": [SOURCE]}
        if path == "/alerts":
            return None
        raise AssertionError(path)

    monkeypatch.setattr(summary, "brightsky_get", fake_get)
    result = runner.invoke(app, ["summary", "Berlin", "--output", "json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["data"]["alerts"] == []
