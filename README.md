# dwdweather Skill

`dwdweather` is a command-line weather tool powered by the BrightSky API using data from the Deutscher Wetterdienst (DWD).

It provides current weather, forecasts, historical observations, DWD alerts, nearby station discovery, and compact summaries for German locations. No API key is required, but internet access is required.

## Installation

Install the runtime project:

```bash
uv tool install ./dwdweather
dwdweather --help
```

Run without installing:

```bash
uv run --project dwdweather dwdweather current Berlin
```

Build and install from a wheel:

```bash
uv build --project dwdweather
uv tool install dwdweather/dist/dwdweather-1.0.0-py3-none-any.whl
```

Run as a standalone PEP 723 script, without `uv sync` or installation (dependencies are declared inline in `dwdweather/run.py`):

```bash
uv run dwdweather/run.py current Berlin
```

## CLI Reference

Usage, command options, output formats, caveats, exit codes, and troubleshooting are documented in the runtime package README: [dwdweather/README.md](dwdweather/README.md).

## Development

The root project is the skill export harness. The installable runtime project lives in `dwdweather/`.

```bash
uv sync
make install
make test
make lint
make typecheck
make check
make run ARGS="current Berlin"
```

Direct commands:

```bash
uv run pytest tests/
uv run ruff check dwdweather
uv run mypy dwdweather
```

## Skill Export

Copy the runtime project into a skill layout:

```bash
./copy-to-skill.sh /path/to/target-skill
/path/to/target-skill/bin/dwdweather --help
```

The generated wrapper runs the copied runtime with `uv run`, keeping it isolated from the caller's active virtual environment.

## License

MIT

## AI Usage

This project was developed with AI assistance and human review/testing.
