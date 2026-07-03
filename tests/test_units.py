from __future__ import annotations

import io
import json
from pathlib import Path

import httpx
import pytest

from dwdweather import cache, geocode, toon
from dwdweather.api import brightsky_get
from dwdweather.commands.alerts import sort_alerts
from dwdweather.commands.common import OutputFormat, resolve_output
from dwdweather.errors import KNOWN_ERRORS, DwdWeatherError
from dwdweather.render import fmt_visibility, fmt_wind, weather_icon
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


def test_resolve_output_explicit_value_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    assert resolve_output(OutputFormat.json) == OutputFormat.json


def test_resolve_output_defaults_to_text_on_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    assert resolve_output(None) == OutputFormat.text


def test_resolve_output_defaults_to_json_when_not_a_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdout.isatty", lambda: False)
    assert resolve_output(None) == OutputFormat.json


def test_toon_dumps_escapes_delimiter_in_strings() -> None:
    text = toon.dumps({"a": "hello, world"})
    assert '"hello, world"' in text


def test_toon_dumps_leaves_plain_strings_unquoted() -> None:
    text = toon.dumps({"a": "plain"})
    assert "a: plain" in text
    assert '"plain"' not in text


def test_toon_dumps_uses_tabular_shape_for_uniform_dict_list() -> None:
    text = toon.dumps([{"a": 1, "b": 2}, {"a": 3, "b": 4}])
    assert "{a,b}" in text
    assert "1,2" in text
    assert "3,4" in text


def test_toon_dumps_falls_back_to_list_items_for_non_uniform_dicts() -> None:
    text = toon.dumps([{"a": 1}, {"a": 1, "b": 2}])
    assert "{a,b}" not in text


def test_toon_dumps_float_formatting() -> None:
    assert toon.dumps({"x": 1.5}).strip() == "x: 1.5"
    assert toon.dumps({"x": 2.0}).strip() == "x: 2"
    assert toon.dumps({"x": -0.0}).strip() == "x: 0"


def test_toon_dumps_raises_on_unsupported_type() -> None:
    with pytest.raises(toon.ToonEncodeError):
        toon.dumps({"x": {1, 2, 3}})


def test_toon_dumps_raises_on_non_finite_float() -> None:
    with pytest.raises(toon.ToonEncodeError):
        toon.dumps({"x": float("inf")})


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


def _http_status_error(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://api.brightsky.dev/weather")
    response = httpx.Response(status, request=request)
    return httpx.HTTPStatusError(f"HTTP {status}", request=request, response=response)


def test_brightsky_429_maps_to_rate_limited(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(*args: object, **kwargs: object) -> httpx.Response:
        raise _http_status_error(429)

    monkeypatch.setattr(httpx, "get", fake_get)
    with pytest.raises(DwdWeatherError) as exc:
        brightsky_get("/weather", {})
    assert exc.value.code == "RATE_LIMITED"
    assert exc.value.suggestion is not None


def test_brightsky_5xx_maps_to_service_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(*args: object, **kwargs: object) -> httpx.Response:
        raise _http_status_error(503)

    monkeypatch.setattr(httpx, "get", fake_get)
    with pytest.raises(DwdWeatherError) as exc:
        brightsky_get("/weather", {})
    assert exc.value.code == "SERVICE_UNAVAILABLE"


def test_brightsky_other_status_maps_to_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(*args: object, **kwargs: object) -> httpx.Response:
        raise _http_status_error(418)

    monkeypatch.setattr(httpx, "get", fake_get)
    with pytest.raises(DwdWeatherError) as exc:
        brightsky_get("/weather", {})
    assert exc.value.code == "API_ERROR"


def test_brightsky_timeout_maps_to_network_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(*args: object, **kwargs: object) -> httpx.Response:
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(httpx, "get", fake_get)
    with pytest.raises(DwdWeatherError) as exc:
        brightsky_get("/weather", {})
    assert exc.value.code == "NETWORK_ERROR"


def test_brightsky_request_error_maps_to_network_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(*args: object, **kwargs: object) -> httpx.Response:
        raise httpx.RequestError("connection failed")

    monkeypatch.setattr(httpx, "get", fake_get)
    with pytest.raises(DwdWeatherError) as exc:
        brightsky_get("/weather", {})
    assert exc.value.code == "NETWORK_ERROR"


def test_brightsky_invalid_json_maps_to_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    request = httpx.Request("GET", "https://api.brightsky.dev/weather")
    response = httpx.Response(200, request=request, content=b"not json")

    def fake_get(*args: object, **kwargs: object) -> httpx.Response:
        return response

    monkeypatch.setattr(httpx, "get", fake_get)
    with pytest.raises(DwdWeatherError) as exc:
        brightsky_get("/weather", {})
    assert exc.value.code == "API_ERROR"


def test_brightsky_optional_swallows_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(*args: object, **kwargs: object) -> httpx.Response:
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(httpx, "get", fake_get)
    assert brightsky_get("/alerts", {}, optional=True) is None


def test_fmt_visibility_branches() -> None:
    assert fmt_visibility(None) == "-"
    assert fmt_visibility(500) == "500 m"
    assert fmt_visibility(5000) == "5.0 km"


def test_fmt_wind_without_direction() -> None:
    assert fmt_wind(None) == "-"
    assert fmt_wind(10.0) == "10.0 km/h"
    assert fmt_wind(10.0, 90) == "10.0 km/h  E"


def test_weather_icon_uses_icon_map_first() -> None:
    assert weather_icon({"icon": "clear-day", "condition": "rain"}) == "☀️"


def test_weather_icon_falls_back_to_condition() -> None:
    assert weather_icon({"icon": "unknown-icon", "condition": "rain"}) == "🌧️"


def test_weather_icon_defaults_when_unknown() -> None:
    assert weather_icon({"icon": "", "condition": ""}) == "🌡️"


@pytest.fixture
def isolated_cache_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setattr(cache, "cache_dir", lambda: tmp_path)
    return tmp_path


def test_cache_roundtrip(isolated_cache_dir: Path) -> None:
    cache.set_cached("geo", "berlin", {"lat": 52.5})
    assert cache.get_cached("geo", "berlin") == {"lat": 52.5}


def test_cache_missing_key_returns_none(isolated_cache_dir: Path) -> None:
    assert cache.get_cached("geo", "atlantis") is None


def test_cache_expired_entry_returns_none_and_deletes_file(isolated_cache_dir: Path) -> None:
    cache.set_cached("geo", "berlin", {"lat": 52.5}, ttl=-1)
    path = cache.cache_path("geo", "berlin")
    assert path.exists()
    assert cache.get_cached("geo", "berlin") is None
    assert not path.exists()


def test_cache_corrupted_file_returns_none(isolated_cache_dir: Path) -> None:
    path = cache.cache_path("geo", "berlin")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not json", encoding="utf-8")
    assert cache.get_cached("geo", "berlin") is None


NOMINATIM_RESULT = {
    "display_name": "Berlin, Deutschland",
    "address": {"city": "Berlin"},
    "lat": "52.52",
    "lon": "13.405",
}


def test_geocode_location_success(monkeypatch: pytest.MonkeyPatch, isolated_cache_dir: Path) -> None:
    request = httpx.Request("GET", "https://nominatim.openstreetmap.org/search")
    response = httpx.Response(200, request=request, json=[NOMINATIM_RESULT])
    monkeypatch.setattr(httpx, "get", lambda *args, **kwargs: response)

    location = geocode.geocode_location("Berlin")
    assert location["short_name"] == "Berlin"
    assert location["lat"] == 52.52
    assert location["source"] == "geocoding"


def test_geocode_location_uses_cache_on_second_call(monkeypatch: pytest.MonkeyPatch, isolated_cache_dir: Path) -> None:
    request = httpx.Request("GET", "https://nominatim.openstreetmap.org/search")
    response = httpx.Response(200, request=request, json=[NOMINATIM_RESULT])
    calls = {"count": 0}

    def fake_get(*args: object, **kwargs: object) -> httpx.Response:
        calls["count"] += 1
        return response

    monkeypatch.setattr(httpx, "get", fake_get)
    geocode.geocode_location("Berlin")
    geocode.geocode_location("berlin")
    assert calls["count"] == 1


def test_geocode_location_not_found(monkeypatch: pytest.MonkeyPatch, isolated_cache_dir: Path) -> None:
    request = httpx.Request("GET", "https://nominatim.openstreetmap.org/search")
    response = httpx.Response(200, request=request, json=[])
    monkeypatch.setattr(httpx, "get", lambda *args, **kwargs: response)

    with pytest.raises(DwdWeatherError) as exc:
        geocode.geocode_location("Atlantis")
    assert exc.value.code == "LOCATION_NOT_FOUND"
    assert exc.value.exit_code == 3


def test_geocode_location_http_error(monkeypatch: pytest.MonkeyPatch, isolated_cache_dir: Path) -> None:
    def fake_get(*args: object, **kwargs: object) -> httpx.Response:
        raise _http_status_error(500)

    monkeypatch.setattr(httpx, "get", fake_get)
    with pytest.raises(DwdWeatherError) as exc:
        geocode.geocode_location("Berlin")
    assert exc.value.code == "GEOCODING_ERROR"


def test_geocode_location_timeout(monkeypatch: pytest.MonkeyPatch, isolated_cache_dir: Path) -> None:
    def fake_get(*args: object, **kwargs: object) -> httpx.Response:
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(httpx, "get", fake_get)
    with pytest.raises(DwdWeatherError) as exc:
        geocode.geocode_location("Berlin")
    assert exc.value.code == "GEOCODING_ERROR"


def test_short_name_falls_back_to_display_name_prefix() -> None:
    assert geocode._short_name({}, "Somewhere, Region, Country") == "Somewhere"


def test_toon_cli_main_reads_stdin_writes_stdout(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"a": 1})))
    exit_code = toon.main([])
    assert exit_code == 0
    assert "a: 1" in capsys.readouterr().out


def test_toon_cli_main_file_io(tmp_path: Path) -> None:
    input_path = tmp_path / "in.json"
    output_path = tmp_path / "out.toon"
    input_path.write_text(json.dumps({"a": 1}), encoding="utf-8")

    exit_code = toon.main([str(input_path), "-o", str(output_path)])
    assert exit_code == 0
    assert "a: 1" in output_path.read_text(encoding="utf-8")


def test_toon_cli_main_invalid_json_exits_1(tmp_path: Path) -> None:
    input_path = tmp_path / "in.json"
    input_path.write_text("not json", encoding="utf-8")

    with pytest.raises(SystemExit) as exc:
        toon.main([str(input_path)])
    assert exc.value.code == 1


# Every DwdWeatherError("<CODE>", ...) raise site in the codebase, kept in sync manually.
ACTUALLY_RAISED_ERROR_CODES = {
    "NO_DATA",
    "LOCATION_NOT_FOUND",
    "RATE_LIMITED",
    "NETWORK_ERROR",
    "SERVICE_UNAVAILABLE",
    "API_ERROR",
    "GEOCODING_ERROR",
}


def test_known_errors_catalog_covers_all_raised_codes() -> None:
    assert ACTUALLY_RAISED_ERROR_CODES <= set(KNOWN_ERRORS.keys())


def test_known_errors_catalog_entries_have_required_fields() -> None:
    for code, entry in KNOWN_ERRORS.items():
        assert isinstance(code, str) and code
        assert set(entry.keys()) == {"message", "exit_code", "recoverable", "suggested_action"}
