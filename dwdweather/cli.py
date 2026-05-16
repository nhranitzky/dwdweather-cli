from __future__ import annotations

import typer

from . import __version__
from .commands import alerts, current, forecast, history, stations, summary
from .config import runtime

app = typer.Typer(
    add_completion=False,
    help="Command-line weather tool powered by BrightSky API using DWD weather data.",
    invoke_without_command=True,
)


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"dwdweather {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    debug: bool = typer.Option(False, "--debug", help="Show tracebacks and request details for handled errors."),
    version: bool | None = typer.Option(
        None,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show the version and exit.",
    ),
) -> None:
    runtime.debug = debug
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()


app.command()(current.current)
app.command()(forecast.forecast)
app.command()(history.history)
app.command()(alerts.alerts)
app.command()(stations.stations)
app.command()(summary.summary)
