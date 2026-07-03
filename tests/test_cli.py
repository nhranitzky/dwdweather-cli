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


def test_default_output_is_json_when_not_a_tty(monkeypatch: pytest.MonkeyPatch, mock_location: None) -> None:
    from dwdweather.commands import current

    monkeypatch.setattr(
        current,
        "brightsky_get",
        lambda path, params: {"weather": WEATHER_RECORD, "sources": [SOURCE]},
    )
    result = runner.invoke(app, ["current", "Berlin"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["location"]["query"] == "Berlin"


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


def test_history_limit_truncates_and_sets_flag(monkeypatch: pytest.MonkeyPatch, mock_location: None) -> None:
    from dwdweather.commands import history

    records = [{**WEATHER_RECORD, "timestamp": f"2026-05-16T{hour:02d}:00:00+02:00"} for hour in range(10)]
    monkeypatch.setattr(history, "brightsky_get", lambda path, params: {"weather": records, "sources": [SOURCE]})
    result = runner.invoke(
        app,
        ["history", "Berlin", "--date", "2026-05-16", "--limit", "3", "--output", "json"],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["meta"]["truncated"] is True
    assert len(payload["data"]["records"]) == 3


def test_history_under_limit_omits_truncated_flag(monkeypatch: pytest.MonkeyPatch, mock_location: None) -> None:
    from dwdweather.commands import history

    records = [{**WEATHER_RECORD, "timestamp": f"2026-05-16T{hour:02d}:00:00+02:00"} for hour in range(3)]
    monkeypatch.setattr(history, "brightsky_get", lambda path, params: {"weather": records, "sources": [SOURCE]})
    result = runner.invoke(
        app,
        ["history", "Berlin", "--date", "2026-05-16", "--limit", "10", "--output", "json"],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert "truncated" not in payload["meta"]
    assert len(payload["data"]["records"]) == 3


def test_json_error_payload_on_stdout(monkeypatch: pytest.MonkeyPatch, mock_location: None) -> None:
    from dwdweather.commands import forecast

    def fail(path: str, params: dict[str, object]) -> dict[str, object]:
        raise DwdWeatherError("NO_DATA", "No forecast data available for this location.", 4)

    monkeypatch.setattr(forecast, "brightsky_get", fail)
    result = runner.invoke(app, ["forecast", "Berlin", "--output", "json"])
    assert result.exit_code == 4
    payload = json.loads(result.stdout)
    assert payload["error"]["code"] == "NO_DATA"


def test_no_data_error_includes_suggestion(monkeypatch: pytest.MonkeyPatch, mock_location: None) -> None:
    from dwdweather.commands import forecast

    monkeypatch.setattr(forecast, "brightsky_get", lambda path, params: {"weather": [], "sources": []})
    result = runner.invoke(app, ["forecast", "Berlin", "--output", "json"])
    assert result.exit_code == 4
    payload = json.loads(result.stdout)
    assert payload["error"]["code"] == "NO_DATA"
    assert "suggestion" in payload["error"]


def test_rate_limited_error_includes_suggestion(monkeypatch: pytest.MonkeyPatch, mock_location: None) -> None:
    from dwdweather.commands import forecast

    def fail(path: str, params: dict[str, object]) -> dict[str, object]:
        raise DwdWeatherError(
            "RATE_LIMITED",
            "Rate limit exceeded. Please try again later.",
            1,
            suggestion="Wait and retry; consider reducing request frequency.",
        )

    monkeypatch.setattr(forecast, "brightsky_get", fail)
    result = runner.invoke(app, ["forecast", "Berlin", "--output", "json"])
    payload = json.loads(result.stdout)
    assert "suggestion" in payload["error"]


def test_network_error_omits_suggestion(monkeypatch: pytest.MonkeyPatch, mock_location: None) -> None:
    from dwdweather.commands import forecast

    def fail(path: str, params: dict[str, object]) -> dict[str, object]:
        raise DwdWeatherError("NETWORK_ERROR", "Network error while contacting BrightSky.", 1)

    monkeypatch.setattr(forecast, "brightsky_get", fail)
    result = runner.invoke(app, ["forecast", "Berlin", "--output", "json"])
    payload = json.loads(result.stdout)
    assert "suggestion" not in payload["error"]


def test_location_not_found_exits_3(monkeypatch: pytest.MonkeyPatch) -> None:
    from dwdweather.commands import common

    def fail(query: str) -> object:
        raise DwdWeatherError("LOCATION_NOT_FOUND", "Location not found in Germany: 'Atlantis'.", 3)

    monkeypatch.setattr(common, "geocode_location", fail)
    result = runner.invoke(app, ["current", "Atlantis", "--output", "text"])
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


def _assert_toon_envelope(output: str, *expected_top_level_keys: str) -> None:
    assert output.startswith("```toon\n")
    assert output.rstrip("\n").endswith("```")
    for key in expected_top_level_keys:
        assert any(line.strip() == f"{key}:" for line in output.splitlines()), f"missing {key!r} in:\n{output}"


def test_current_toon_success(monkeypatch: pytest.MonkeyPatch, mock_location: None) -> None:
    from dwdweather.commands import current

    monkeypatch.setattr(
        current,
        "brightsky_get",
        lambda path, params: {"weather": WEATHER_RECORD, "sources": [SOURCE]},
    )
    result = runner.invoke(app, ["current", "Berlin", "--output", "toon"])
    assert result.exit_code == 0
    _assert_toon_envelope(result.stdout, "meta", "location", "data")


def test_forecast_toon_success(monkeypatch: pytest.MonkeyPatch, mock_location: None) -> None:
    from dwdweather.commands import forecast

    monkeypatch.setattr(
        forecast,
        "brightsky_get",
        lambda path, params: {"weather": [WEATHER_RECORD], "sources": [SOURCE]},
    )
    result = runner.invoke(app, ["forecast", "Berlin", "--output", "toon"])
    assert result.exit_code == 0
    _assert_toon_envelope(result.stdout, "meta", "location", "data")


def test_history_toon_success(monkeypatch: pytest.MonkeyPatch, mock_location: None) -> None:
    from dwdweather.commands import history

    monkeypatch.setattr(
        history,
        "brightsky_get",
        lambda path, params: {"weather": [WEATHER_RECORD], "sources": [SOURCE]},
    )
    result = runner.invoke(app, ["history", "Berlin", "--date", "2026-05-16", "--output", "toon"])
    assert result.exit_code == 0
    _assert_toon_envelope(result.stdout, "meta", "location", "data")


def test_alerts_toon_success(monkeypatch: pytest.MonkeyPatch, mock_location: None) -> None:
    from dwdweather.commands import alerts

    monkeypatch.setattr(alerts, "brightsky_get", lambda path, params: {"alerts": [], "location": {}})
    result = runner.invoke(app, ["alerts", "Berlin", "--output", "toon"])
    assert result.exit_code == 0
    _assert_toon_envelope(result.stdout, "meta", "location", "data")


def test_stations_toon_success(monkeypatch: pytest.MonkeyPatch, mock_location: None) -> None:
    from dwdweather.commands import stations

    monkeypatch.setattr(stations, "brightsky_get", lambda path, params: {"sources": [SOURCE]})
    result = runner.invoke(app, ["stations", "Berlin", "--output", "toon"])
    assert result.exit_code == 0
    _assert_toon_envelope(result.stdout, "meta", "location", "data")


def test_summary_toon_success(monkeypatch: pytest.MonkeyPatch, mock_location: None) -> None:
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
    result = runner.invoke(app, ["summary", "Berlin", "--output", "toon"])
    assert result.exit_code == 0
    _assert_toon_envelope(result.stdout, "meta", "location", "data")


def test_toon_error_payload_has_code_and_suggestion(monkeypatch: pytest.MonkeyPatch) -> None:
    from dwdweather.commands import common

    def fail(query: str) -> object:
        raise DwdWeatherError(
            "LOCATION_NOT_FOUND",
            "Location not found in Germany: 'Atlantis'.",
            3,
            suggestion="Check the spelling, or use a nearby larger town/city.",
        )

    monkeypatch.setattr(common, "geocode_location", fail)
    result = runner.invoke(app, ["current", "Atlantis", "--output", "toon"])
    assert result.exit_code == 3
    assert result.stdout.startswith("```toon\n")
    assert "code: LOCATION_NOT_FOUND" in result.stdout
    assert "suggestion:" in result.stdout


ALERT = {
    "severity": "severe",
    "headline": "Heavy Thunderstorm Warning",
    "event": "thunderstorm",
    "description": "Severe thunderstorms expected.",
    "instruction": "Stay indoors.",
    "onset": "2026-05-16T12:00:00+02:00",
    "expires": "2026-05-16T18:00:00+02:00",
}


def test_current_text_success(monkeypatch: pytest.MonkeyPatch, mock_location: None) -> None:
    from dwdweather.commands import current

    monkeypatch.setattr(
        current,
        "brightsky_get",
        lambda path, params: {"weather": WEATHER_RECORD, "sources": [SOURCE]},
    )
    result = runner.invoke(app, ["current", "Berlin", "--output", "text"])
    assert result.exit_code == 0
    assert "Current Weather" in result.stdout


def test_forecast_text_hourly_success(monkeypatch: pytest.MonkeyPatch, mock_location: None) -> None:
    from dwdweather.commands import forecast

    monkeypatch.setattr(
        forecast,
        "brightsky_get",
        lambda path, params: {"weather": [WEATHER_RECORD], "sources": [SOURCE]},
    )
    result = runner.invoke(app, ["forecast", "Berlin", "--output", "text"])
    assert result.exit_code == 0
    assert "Hourly Forecast" in result.stdout


def test_forecast_text_daily_success(monkeypatch: pytest.MonkeyPatch, mock_location: None) -> None:
    from dwdweather.commands import forecast

    monkeypatch.setattr(
        forecast,
        "brightsky_get",
        lambda path, params: {"weather": [WEATHER_RECORD], "sources": [SOURCE]},
    )
    result = runner.invoke(app, ["forecast", "Berlin", "--daily", "--output", "text"])
    assert result.exit_code == 0
    assert "Daily Forecast" in result.stdout


def test_history_text_hourly_success(monkeypatch: pytest.MonkeyPatch, mock_location: None) -> None:
    from dwdweather.commands import history

    monkeypatch.setattr(
        history,
        "brightsky_get",
        lambda path, params: {"weather": [WEATHER_RECORD], "sources": [SOURCE]},
    )
    result = runner.invoke(app, ["history", "Berlin", "--date", "2026-05-16", "--output", "text"])
    assert result.exit_code == 0
    assert "Historical Weather" in result.stdout


def test_history_text_daily_success(monkeypatch: pytest.MonkeyPatch, mock_location: None) -> None:
    from dwdweather.commands import history

    monkeypatch.setattr(
        history,
        "brightsky_get",
        lambda path, params: {"weather": [WEATHER_RECORD], "sources": [SOURCE]},
    )
    result = runner.invoke(app, ["history", "Berlin", "--date", "2026-05-16", "--daily", "--output", "text"])
    assert result.exit_code == 0
    assert "Historical Daily Summary" in result.stdout


def test_history_text_shows_truncated_hint(monkeypatch: pytest.MonkeyPatch, mock_location: None) -> None:
    from dwdweather.commands import history

    records = [{**WEATHER_RECORD, "timestamp": f"2026-05-16T{hour:02d}:00:00+02:00"} for hour in range(5)]
    monkeypatch.setattr(history, "brightsky_get", lambda path, params: {"weather": records, "sources": [SOURCE]})
    result = runner.invoke(
        app, ["history", "Berlin", "--date", "2026-05-16", "--limit", "2", "--output", "text"]
    )
    assert result.exit_code == 0
    assert "truncated" in result.stdout.lower()


def test_stations_text_success(monkeypatch: pytest.MonkeyPatch, mock_location: None) -> None:
    from dwdweather.commands import stations

    monkeypatch.setattr(stations, "brightsky_get", lambda path, params: {"sources": [SOURCE]})
    result = runner.invoke(app, ["stations", "Berlin", "--output", "text"])
    assert result.exit_code == 0
    assert "DWD Stations near Berlin" in result.stdout


def test_summary_text_with_alert(monkeypatch: pytest.MonkeyPatch, mock_location: None) -> None:
    from dwdweather.commands import summary

    def fake_get(path: str, params: dict[str, object], optional: bool = False) -> dict[str, object] | None:
        if path == "/current_weather":
            return {"weather": WEATHER_RECORD, "sources": [SOURCE]}
        if path == "/weather":
            return {"weather": [WEATHER_RECORD], "sources": [SOURCE]}
        if path == "/alerts":
            return {"alerts": [ALERT]}
        raise AssertionError(path)

    monkeypatch.setattr(summary, "brightsky_get", fake_get)
    result = runner.invoke(app, ["summary", "Berlin", "--output", "text"])
    assert result.exit_code == 0
    assert "Now" in result.stdout
    assert "Heavy Thunderstorm Warning" in result.stdout


def test_alerts_text_with_active_alert(monkeypatch: pytest.MonkeyPatch, mock_location: None) -> None:
    from dwdweather.commands import alerts

    monkeypatch.setattr(
        alerts,
        "brightsky_get",
        lambda path, params: {"alerts": [ALERT], "location": {"name": "Berlin", "warn_cell_id": "803159016"}},
    )
    result = runner.invoke(app, ["alerts", "Berlin", "--output", "text"])
    assert result.exit_code == 0
    assert "HEAVY THUNDERSTORM WARNING" in result.stdout


def test_alerts_text_no_active_alert(monkeypatch: pytest.MonkeyPatch, mock_location: None) -> None:
    from dwdweather.commands import alerts

    monkeypatch.setattr(
        alerts,
        "brightsky_get",
        lambda path, params: {"alerts": [], "location": {"name": "Berlin", "warn_cell_id": "803159016"}},
    )
    result = runner.invoke(app, ["alerts", "Berlin", "--output", "text"])
    assert result.exit_code == 0
    assert "No active weather warnings." in result.stdout


def test_alerts_text_outside_germany(monkeypatch: pytest.MonkeyPatch, mock_location: None) -> None:
    from dwdweather.commands import alerts

    monkeypatch.setattr(alerts, "brightsky_get", lambda path, params: {"alerts": [], "location": {}})
    result = runner.invoke(app, ["alerts", "Berlin", "--output", "text"])
    assert result.exit_code == 0
    assert "only available for locations within Germany" in result.stdout


def _fail_with_details(monkeypatch: pytest.MonkeyPatch) -> None:
    from dwdweather.commands import common

    def fail(query: str) -> object:
        raise DwdWeatherError("NO_DATA", "No data available.", 4, details="GET /weather returned HTTP 404")

    monkeypatch.setattr(common, "geocode_location", fail)


def test_debug_shows_details_in_text_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    _fail_with_details(monkeypatch)
    result = runner.invoke(app, ["--debug", "current", "Berlin", "--output", "text"])
    assert result.exit_code == 4
    assert "GET /weather returned HTTP 404" in result.stderr


def test_debug_shows_details_in_json_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    _fail_with_details(monkeypatch)
    result = runner.invoke(app, ["--debug", "current", "Berlin", "--output", "json"])
    assert result.exit_code == 4
    assert "GET /weather returned HTTP 404" in result.stderr


def test_debug_shows_details_in_toon_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    _fail_with_details(monkeypatch)
    result = runner.invoke(app, ["--debug", "current", "Berlin", "--output", "toon"])
    assert result.exit_code == 4
    assert "GET /weather returned HTTP 404" in result.stderr


def test_commands_list_json_success() -> None:
    result = runner.invoke(app, ["commands", "list", "--output", "json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["meta"]["command"] == "commands"
    names = [command["name"] for command in payload["data"]["commands"]]
    assert names == ["alerts", "current", "forecast", "history", "stations", "summary"]


def test_commands_list_json_describes_option_shape() -> None:
    result = runner.invoke(app, ["commands", "list", "--output", "json"])
    payload = json.loads(result.stdout)
    history_schema = next(c for c in payload["data"]["commands"] if c["name"] == "history")
    date_option = next(o for o in history_schema["options"] if o["flags"] == ["--date"])
    assert date_option["required"] is True
    limit_option = next(o for o in history_schema["options"] if o["flags"] == ["--limit"])
    assert limit_option["type"] == "integer"
    assert limit_option["default"] == 8784
    output_option = next(o for o in history_schema["options"] if o["flags"] == ["--output"])
    assert output_option["choices"] == ["text", "json", "toon"]
    location_argument = history_schema["arguments"][0]
    assert location_argument["variadic"] is True
    assert location_argument["required"] is True


def test_commands_list_excludes_itself() -> None:
    result = runner.invoke(app, ["commands", "list", "--output", "json"])
    payload = json.loads(result.stdout)
    names = [command["name"] for command in payload["data"]["commands"]]
    assert "commands" not in names


def test_commands_list_toon_success() -> None:
    result = runner.invoke(app, ["commands", "list", "--output", "toon"])
    assert result.exit_code == 0
    assert result.stdout.startswith("```toon\n")
    assert "name: current" in result.stdout


def test_commands_list_text_success() -> None:
    result = runner.invoke(app, ["commands", "list", "--output", "text"])
    assert result.exit_code == 0
    assert "Available Commands" in result.stdout
    assert "current" in result.stdout
    assert "6 command(s)" in result.stdout
