from __future__ import annotations

from typing import Any, TypedDict, cast

import httpx

from . import __version__
from .cache import get_cached, set_cached
from .errors import DwdWeatherError

NOMINATIM_BASE = "https://nominatim.openstreetmap.org"
GEOCODING_TIMEOUT = 10.0


class Location(TypedDict):
    query: str
    name: str
    short_name: str
    lat: float
    lon: float
    source: str


def geocode_location(query: str) -> Location:
    normalized_key = " ".join(query.casefold().split())
    cached = get_cached("geo", normalized_key)
    if cached:
        return cached  # type: ignore[return-value]

    headers = {"User-Agent": f"dwdweather/{__version__}"}
    params: dict[str, str | int] = {
        "q": query,
        "format": "jsonv2",
        "limit": 1,
        "countrycodes": "de",
        "addressdetails": 1,
    }
    try:
        response = httpx.get(f"{NOMINATIM_BASE}/search", params=params, headers=headers, timeout=GEOCODING_TIMEOUT)
        response.raise_for_status()
        results = cast(list[dict[str, Any]], response.json())
    except httpx.HTTPStatusError as exc:
        details = f"GET {exc.request.url} returned HTTP {exc.response.status_code}"
        raise DwdWeatherError("GEOCODING_ERROR", "Geocoding service returned an error.", 1, details) from exc
    except httpx.TimeoutException as exc:
        raise DwdWeatherError("GEOCODING_ERROR", "Network timeout while geocoding location.", 1, str(exc)) from exc
    except httpx.RequestError as exc:
        raise DwdWeatherError("GEOCODING_ERROR", "Network error while geocoding location.", 1, str(exc)) from exc
    except ValueError as exc:
        raise DwdWeatherError("GEOCODING_ERROR", "Geocoding service returned invalid JSON.", 1, str(exc)) from exc

    if not results:
        raise DwdWeatherError("LOCATION_NOT_FOUND", f"Location not found in Germany: {query!r}.", 3)

    location = _normalize_location(query, results[0])
    set_cached("geo", normalized_key, dict(location))
    return location


def _normalize_location(query: str, result: dict[str, Any]) -> Location:
    display_name = str(result.get("display_name") or query)
    address = result.get("address") or {}
    short_name = _short_name(address, display_name)
    return {
        "query": query,
        "name": display_name,
        "short_name": short_name,
        "lat": float(result["lat"]),
        "lon": float(result["lon"]),
        "source": "geocoding",
    }


def _short_name(address: dict[str, Any], display_name: str) -> str:
    for key in ("city", "town", "village", "municipality", "suburb"):
        value = address.get(key)
        if value:
            return str(value)
    return display_name.split(",", 1)[0].strip()
