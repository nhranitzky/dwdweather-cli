from __future__ import annotations

from typing import Any

import click
import typer

from dwdweather.render import echo_json, echo_toon, render_commands

from .common import OutputFormat, OutputOption, meta, resolve_output

commands_app = typer.Typer(help="Machine-readable command discovery for agents.", no_args_is_help=True)


def _type_name(param_type: click.ParamType) -> str:
    if isinstance(param_type, click.Choice):
        return "choice"
    if isinstance(param_type, click.types.BoolParamType):
        return "boolean"
    if isinstance(param_type, click.types.IntParamType):
        return "integer"
    if isinstance(param_type, click.types.FloatParamType):
        return "number"
    return "string"


def _argument_schema(param: click.Argument) -> dict[str, Any]:
    return {
        "name": param.name,
        "required": bool(param.required),
        "variadic": param.nargs == -1,
        "type": _type_name(param.type),
        "help": getattr(param, "help", None),
    }


def _option_schema(param: click.Option) -> dict[str, Any]:
    schema: dict[str, Any] = {
        "flags": list(param.opts),
        "type": _type_name(param.type),
        "required": bool(param.required),
        "default": param.default,
        "help": param.help,
    }
    if param.envvar:
        schema["envvar"] = param.envvar
    if isinstance(param.type, click.Choice):
        schema["choices"] = list(param.type.choices)
    if isinstance(param.type, click.types.IntRange | click.types.FloatRange):
        schema["min"] = param.type.min
        schema["max"] = param.type.max
    return schema


def _command_schema(name: str, command: click.Command) -> dict[str, Any]:
    arguments = [_argument_schema(p) for p in command.params if isinstance(p, click.Argument)]
    options = [_option_schema(p) for p in command.params if isinstance(p, click.Option)]
    return {
        "name": name,
        "help": (command.help or command.short_help or "").strip(),
        "arguments": arguments,
        "options": options,
    }


def build_command_schema() -> list[dict[str, Any]]:
    from dwdweather.cli import app  # deferred import breaks the cli.py <-> discovery.py import cycle

    root = typer.main.get_command(app)
    if not isinstance(root, click.Group):
        return []
    return [
        _command_schema(name, command)
        for name, command in sorted(root.commands.items())
        if not isinstance(command, click.Group)
    ]


def list_commands(output: OutputOption = None) -> None:
    """List all available commands with their arguments, options, and help text."""
    output = resolve_output(output)
    command_schemas = build_command_schema()
    if output in (OutputFormat.json, OutputFormat.toon):
        payload = {
            "meta": meta("commands", "list"),
            "data": {"commands": command_schemas},
        }
        if output == OutputFormat.toon:
            echo_toon(payload)
        else:
            echo_json(payload)
        return
    render_commands(command_schemas)


commands_app.command("list")(list_commands)
