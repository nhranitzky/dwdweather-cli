from __future__ import annotations

from typing import Any, cast

import httpx

from .errors import DwdWeatherError

BRIGHTSKY_BASE = "https://api.brightsky.dev"
BRIGHTSKY_TIMEOUT = 15.0


def brightsky_get(path: str, params: dict[str, Any], *, optional: bool = False) -> dict[str, Any] | None:
    url = f"{BRIGHTSKY_BASE}{path}"
    try:
        response = httpx.get(url, params=params, timeout=BRIGHTSKY_TIMEOUT)
        response.raise_for_status()
        return cast(dict[str, Any], response.json())
    except httpx.HTTPStatusError as exc:
        if optional:
            return None
        status = exc.response.status_code
        details = f"GET {exc.request.url} returned HTTP {status}"
        if status == 404:
            raise DwdWeatherError("NO_DATA", "No data available for this request.", 4, details) from exc
        if status == 429:
            raise DwdWeatherError("RATE_LIMITED", "Rate limit exceeded. Please try again later.", 1, details) from exc
        if 500 <= status < 600:
            raise DwdWeatherError(
                "SERVICE_UNAVAILABLE",
                f"BrightSky is unavailable (HTTP {status}). Please try again later.",
                1,
                details,
            ) from exc
        raise DwdWeatherError("API_ERROR", f"BrightSky API error (HTTP {status}).", 1, details) from exc
    except httpx.TimeoutException as exc:
        if optional:
            return None
        raise DwdWeatherError("NETWORK_ERROR", "Network timeout while contacting BrightSky.", 1, str(exc)) from exc
    except httpx.RequestError as exc:
        if optional:
            return None
        raise DwdWeatherError("NETWORK_ERROR", "Network error while contacting BrightSky.", 1, str(exc)) from exc
    except ValueError as exc:
        if optional:
            return None
        raise DwdWeatherError("API_ERROR", "BrightSky returned an invalid JSON response.", 1, str(exc)) from exc
