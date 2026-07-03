# dwdweather

`dwdweather` is a command-line weather tool powered by the BrightSky API using data from the Deutscher Wetterdienst (DWD).

It provides current weather, forecasts, historical observations, DWD alerts, nearby station discovery, and compact summaries for German locations. No API key is required, but internet access is required.

 

## Command Overview

```text
dwdweather current   LOCATION... [--tz TZ] [--output text|json|toon]
dwdweather forecast  LOCATION... [--days N] [--daily] [--tz TZ] [--output text|json|toon]
dwdweather history   LOCATION... --date YYYY-MM-DD [--end-date YYYY-MM-DD] [--daily] [--tz TZ] [--limit N] [--output text|json|toon]
dwdweather alerts    LOCATION... [--output text|json|toon]
dwdweather stations  LOCATION... [--radius KM] [--limit N] [--output text|json|toon]
dwdweather summary   LOCATION... [--days N] [--tz TZ] [--output text|json|toon]
dwdweather commands list [--output text|json|toon]
```

All weather commands require a German location name. Multi-word locations may be passed unquoted.

## Global Options

- `--version`: print `dwdweather 1.0.0`
- `--debug`: show tracebacks and request details for handled errors

## Common Options

- `--output text|json|toon`: output format; `toon` emits TOON v3.0 wrapped in a ` ```toon ` code fence. If omitted, the default depends on whether stdout is an interactive terminal: `text` when interactive, `json` otherwise (e.g. when piped or called by another program/agent).
- `--tz TIMEZONE`: timezone for weather timestamps, default `Europe/Berlin`

`DWDWEATHER_TZ` can set the default timezone when `--tz` is not passed.

The CLI uses DWD/BrightSky default units only: Celsius, km/h, mm, hPa, meters/kilometers, and minutes.

## Output

Successful JSON uses a stable wrapper:

```json
{
  "meta": {
    "command": "forecast",
    "mode": "hourly",
    "timezone": "Europe/Berlin",
    "generated_at": "2026-05-16T12:34:56+00:00"
  },
  "location": {
    "query": "Berlin",
    "name": "Berlin, Deutschland",
    "short_name": "Berlin",
    "lat": 52.52,
    "lon": 13.405,
    "source": "geocoding"
  },
  "data": {}
}
```

Handled JSON errors are printed to stdout:

```json
{
  "error": {
    "code": "NO_DATA",
    "message": "No forecast data available for this location.",
    "exit_code": 4,
    "suggestion": "Check the location and date range, or list nearby stations with `dwdweather stations`."
  }
}
```

The `suggestion` field is only present for actionable errors (`LOCATION_NOT_FOUND`, `NO_DATA`, `RATE_LIMITED`); it is omitted for infrastructure errors such as `NETWORK_ERROR` or `SERVICE_UNAVAILABLE`.

`--output toon` emits the same structure in TOON v3.0 format, which is typically 20–60% smaller depending on data shape. Errors are also emitted as TOON when this format is selected. The output is wrapped in a ` ```toon ` / ` ``` ` code fence for direct embedding in Markdown.

Successful TOON output:

````
```toon
meta:
  command: forecast
  mode: hourly
  timezone: Europe/Berlin
  generated_at: "2026-05-16T12:34:56+00:00"
location:
  query: Berlin
  name: "Berlin, Deutschland"
  short_name: Berlin
  lat: 52.52
  lon: 13.405
  source: geocoding
data:
```
````

Handled TOON errors:

````
```toon
error:
  code: NO_DATA
  message: No forecast data available for this location.
  exit_code: 4
```
````

## Commands

### `current`

Shows current weather from BrightSky `/current_weather`.

Text output includes observed timestamp, temperature, dew point, humidity, wind, gusts, recent precipitation, cloud cover, pressure, visibility, sunshine, and station information.

JSON data:

```json
{
  "weather": {},
  "source": {}
}
```

### `forecast`

Shows forecast data from BrightSky `/weather`.

Options:

- `--days`: `1..10`, default `3`
- `--daily`: aggregate to daily rows
- `--tz`: timezone, default `Europe/Berlin` or `DWDWEATHER_TZ`

Default mode is hourly. `--daily` affects text and JSON.

### `history`

Shows historical observations from BrightSky `/weather`.

Options:

- `--date`: required `YYYY-MM-DD`
- `--end-date`: inclusive end date, `YYYY-MM-DD`
- `--daily`: aggregate to daily rows
- `--tz`: timezone, default `Europe/Berlin` or `DWDWEATHER_TZ`
- `--limit`: maximum number of hourly records returned, default `8784` (366 days of hourly data); applies before `--daily` aggregation

Date ranges are capped at 366 days. If the number of hourly records exceeds `--limit`, the result is cut off and `meta.truncated` is set to `true` in JSON/TOON output (a hint is also printed in text mode).

### `alerts`

Shows active DWD alerts from BrightSky `/alerts`.

No active alerts is a successful result. Alerts are sorted by severity descending, then onset ascending.

### `stations`

Lists DWD stations from BrightSky `/sources`.

Options:

- `--radius`: `1..1000` km, default `50`
- `--limit`: `1..100`, default `15`

Stations are sorted by distance ascending before the limit is applied.

### `summary`

Shows current conditions, a daily outlook, and best-effort active alerts. Alert lookup failure does not fail the whole summary if current weather and forecast data succeed.

Options:

- `--days`: `1..10`, default `5`
- `--tz`: timezone, default `Europe/Berlin` or `DWDWEATHER_TZ`

### `commands list`

Machine-readable command discovery: lists every weather command with its arguments and options (flags, type, required/default, choices, env var), without needing to parse `--help` text. Intended for agents introspecting this CLI programmatically.

```json
{
  "meta": {"command": "commands", "mode": "list", "generated_at": "..."},
  "data": {
    "commands": [
      {
        "name": "current",
        "help": "Show current weather for LOCATION.",
        "arguments": [
          {"name": "location", "required": true, "variadic": true, "type": "string", "help": "..."}
        ],
        "options": [
          {"flags": ["--tz"], "type": "string", "required": false, "default": null, "help": "...", "envvar": "DWDWEATHER_TZ"},
          {"flags": ["--output"], "type": "choice", "required": false, "default": null, "help": "...", "choices": ["text", "json", "toon"]}
        ]
      }
    ]
  }
}
```

## Caveats

- Data comes from DWD through BrightSky.
- Location-name geocoding is restricted to Germany.
- Alerts are DWD warnings and Germany-only.
- Weather and geocoding requests require internet access.
- Geocoding results are cached for 7 days in the platform-native user cache directory.

## Exit Codes

- `0`: success
- `1`: general runtime/API/network error
- `2`: CLI usage or validation error
- `3`: location not found
- `4`: no weather/station data for valid input

## Troubleshooting

- Location not found: location-name search is restricted to Germany.
- No alerts: this is normal and exits `0`.
- Alerts unavailable: DWD alerts are Germany-only.
- Invalid timezone: use an IANA name such as `Europe/Berlin` or `UTC`.
- No data for history: check the date range and nearby station coverage with `stations`.
