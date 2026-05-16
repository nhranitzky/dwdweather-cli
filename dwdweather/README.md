# dwdweather

`dwdweather` is a command-line weather tool powered by the BrightSky API using data from the Deutscher Wetterdienst (DWD).

It provides current weather, forecasts, historical observations, DWD alerts, nearby station discovery, and compact summaries for German locations. No API key is required, but internet access is required.

 

## Command Overview

```text
dwdweather current   LOCATION... [--tz TZ] [--output text|json]
dwdweather forecast  LOCATION... [--days N] [--daily] [--tz TZ] [--output text|json]
dwdweather history   LOCATION... --date YYYY-MM-DD [--end-date YYYY-MM-DD] [--daily] [--tz TZ] [--output text|json]
dwdweather alerts    LOCATION... [--output text|json]
dwdweather stations  LOCATION... [--radius KM] [--limit N] [--output text|json]
dwdweather summary   LOCATION... [--days N] [--tz TZ] [--output text|json]
```

All commands require a German location name. Multi-word locations may be passed unquoted.

## Global Options

- `--version`: print `dwdweather 1.0.0`
- `--debug`: show tracebacks and request details for handled errors

## Common Options

- `--output text|json`: output format, default `text`
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
    "exit_code": 4
  }
}
```

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

- `--days`, `-d`: `1..10`, default `3`
- `--daily`: aggregate to daily rows
- `--tz`: timezone, default `Europe/Berlin` or `DWDWEATHER_TZ`

Default mode is hourly. `--daily` affects text and JSON.

### `history`

Shows historical observations from BrightSky `/weather`.

Options:

- `--date`, `-d`: required `YYYY-MM-DD`
- `--end-date`, `-e`: inclusive end date, `YYYY-MM-DD`
- `--daily`: aggregate to daily rows
- `--tz`: timezone, default `Europe/Berlin` or `DWDWEATHER_TZ`

Date ranges are capped at 366 days.

### `alerts`

Shows active DWD alerts from BrightSky `/alerts`.

No active alerts is a successful result. Alerts are sorted by severity descending, then onset ascending.

### `stations`

Lists DWD stations from BrightSky `/sources`.

Options:

- `--radius`, `-r`: `1..1000` km, default `50`
- `--limit`, `-n`: `1..100`, default `15`

Stations are sorted by distance ascending before the limit is applied.

### `summary`

Shows current conditions, a daily outlook, and best-effort active alerts. Alert lookup failure does not fail the whole summary if current weather and forecast data succeed.

Options:

- `--days`, `-d`: `1..10`, default `5`
- `--tz`: timezone, default `Europe/Berlin` or `DWDWEATHER_TZ`

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
