from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any

import typer

from dwdweather import __version__
from dwdweather.errors import EXIT_CODES, KNOWN_ERRORS
from dwdweather.render import echo_json

SCHEMA_VERSION = "1.0"

_EFFECTS: dict[str, Any] = {
    "reads_files": False,
    "writes_files": True,
    "uses_network": True,
    "mutates_local_state": True,
    "mutates_remote_state": False,
}

_SAFETY: dict[str, Any] = {
    "risk_level": "low",
    "destructive": False,
    "requires_confirmation": False,
}

_PRECONDITIONS: list[str] = [
    "Internet access is required.",
    "LOCATION must resolve to a place in Germany (geocoding is restricted to Germany).",
]

_ERRORS: list[dict[str, Any]] = [{"code": code, **details} for code, details in KNOWN_ERRORS.items()]

_EXAMPLES: dict[str, list[dict[str, Any]]] = {
    "current": [
        {"description": "Show current weather for Berlin.", "command": "dwdweather current Berlin", "safe": True}
    ],
    "forecast": [
        {
            "description": "Show a 3-day hourly forecast for Berlin.",
            "command": "dwdweather forecast Berlin --days 3",
            "safe": True,
        }
    ],
    "history": [
        {
            "description": "Show historical weather for Berlin on a single date.",
            "command": "dwdweather history Berlin --date 2026-01-01",
            "safe": True,
        }
    ],
    "alerts": [
        {
            "description": "Show active DWD weather warnings for Berlin.",
            "command": "dwdweather alerts Berlin",
            "safe": True,
        }
    ],
    "stations": [
        {
            "description": "List DWD stations within 50 km of Berlin.",
            "command": "dwdweather stations Berlin --radius 50",
            "safe": True,
        }
    ],
    "summary": [
        {
            "description": "Show a compact weather summary for Berlin.",
            "command": "dwdweather summary Berlin",
            "safe": True,
        }
    ],
}

_DATA_PROPERTIES: dict[str, dict[str, Any]] = {
    "current": {
        "weather": {"type": "object"},
        "source": {"type": "object"},
    },
    "forecast": {
        "source": {"type": "object"},
        "records": {"type": "array"},
    },
    "history": {
        "period": {"type": "string"},
        "sources": {"type": "array"},
        "records": {"type": "array"},
    },
    "alerts": {
        "municipality": {"type": "string"},
        "warn_cell_id": {"type": "string"},
        "alerts": {"type": "array"},
    },
    "stations": {
        "radius_km": {"type": "integer"},
        "limit": {"type": "integer"},
        "stations": {"type": "array"},
    },
    "summary": {
        "current": {"type": "object"},
        "current_source": {"type": "object"},
        "forecast": {"type": "array"},
        "alerts": {"type": "array"},
    },
}


class DescribeFormat(StrEnum):
    markdown = "markdown"
    json = "json"


# Typer builds its command tree on top of Click, but which Click implementation backs it
# (the standalone `click` package vs. a version that vendors its own copy internally) has
# changed across Typer releases. Introspecting via `isinstance(p, click.Argument)` against
# either implementation is therefore version-fragile. Click's Parameter/ParamType objects
# expose the same small, stable attribute surface (`param_type_name`, `.type.name`,
# `.context_class`, `hasattr(..., "choices"/"min"/"max"/"commands")`) regardless of which
# Click flavor Typer uses underneath, so duck typing on those attributes is used instead of
# importing `click` directly.


def _type_name(param_type: Any) -> str:
    if hasattr(param_type, "choices"):
        return "choice"
    name = str(getattr(param_type, "name", ""))
    if name == "boolean":
        return "boolean"
    if "integer" in name:
        return "integer"
    if "float" in name:
        return "number"
    return "string"


def _argument_schema(param: Any) -> dict[str, Any]:
    return {
        "name": param.name,
        "aliases": [],
        "type": _type_name(param.type),
        "required": bool(param.required),
        "variadic": param.nargs == -1,
        "default": param.default,
        "enum": None,
        "description": getattr(param, "help", None),
        "examples": [],
        "sensitive": False,
        "deprecated": False,
        "hidden": False,
    }


def _option_schema(param: Any) -> dict[str, Any]:
    choices = getattr(param.type, "choices", None)
    schema: dict[str, Any] = {
        "name": param.opts[0],
        "aliases": list(param.opts[1:]),
        "type": _type_name(param.type),
        "required": bool(param.required),
        "default": param.default,
        "enum": list(choices) if choices is not None else None,
        "description": param.help,
        "examples": [],
        "sensitive": False,
        "deprecated": False,
        "hidden": False,
    }
    if param.envvar:
        schema["envvar"] = param.envvar
    if hasattr(param.type, "min") and hasattr(param.type, "max"):
        schema["min"] = param.type.min
        schema["max"] = param.type.max
    return schema


def _usage(name: str, command: Any) -> str:
    ctx = command.context_class(command, info_name=f"dwdweather {name}")
    return str(command.get_usage(ctx)).removeprefix("Usage: ")


def _command_schema(name: str, command: Any) -> dict[str, Any]:
    arguments = [_argument_schema(p) for p in command.params if getattr(p, "param_type_name", None) == "argument"]
    options = [_option_schema(p) for p in command.params if getattr(p, "param_type_name", None) == "option"]
    summary = (command.help or command.short_help or "").strip()
    data_schema = {
        "type": "object",
        "properties": {
            "meta": {"type": "object"},
            "location": {"type": "object"},
            "data": {"type": "object", "properties": _DATA_PROPERTIES.get(name, {})},
        },
        "required": ["meta", "location", "data"],
    }
    return {
        "name": name,
        "summary": summary,
        "description": summary,
        "usage": _usage(name, command),
        "arguments": arguments,
        "options": options,
        "examples": _EXAMPLES.get(name, []),
        "preconditions": _PRECONDITIONS,
        "effects": _EFFECTS,
        "safety": _SAFETY,
        "idempotent": True,
        "mutates_state": True,
        "requires_network": True,
        "supports_dry_run": False,
        "output": {
            "default_format": "text",
            "formats": ["text", "json", "toon"],
            "json_schema": data_schema,
        },
        "exit_codes": EXIT_CODES,
        "errors": _ERRORS,
    }


def _weather_commands() -> dict[str, Any]:
    from dwdweather.cli import app  # deferred import breaks the cli.py <-> describe.py import cycle

    root = typer.main.get_command(app)
    if not hasattr(root, "commands"):
        return {}
    return {
        name: command
        for name, command in root.commands.items()
        if not hasattr(command, "commands") and name != "describe"
    }


def build_root_description() -> dict[str, Any]:
    from dwdweather.cli import app  # deferred import breaks the cli.py <-> describe.py import cycle

    root = typer.main.get_command(app)
    global_options = [
        _option_schema(p) for p in root.params if getattr(p, "param_type_name", None) == "option"
    ]
    summary = (root.help or "").strip()
    commands = [_command_schema(name, command) for name, command in sorted(_weather_commands().items())]
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "cli.describe",
        "name": "dwdweather",
        "version": __version__,
        "summary": summary,
        "description": summary,
        "global_options": global_options,
        "commands": commands,
        "environment_variables": [
            {
                "name": "DWDWEATHER_TZ",
                "required": False,
                "default": "Europe/Berlin",
                "description": "Default timezone for weather timestamps when --tz is not passed.",
            }
        ],
        "config_files": [],
        "authentication": None,
        "output_formats": ["text", "json", "toon"],
    }


def _md_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return lines


def render_root_markdown(root: dict[str, Any]) -> str:
    lines = [f"# {root['name']}", "", root["summary"], "", "## Description", "", root["description"], ""]

    lines.append("## Global Options")
    lines.append("")
    lines.extend(
        _md_table(
            ["Option", "Type", "Required", "Default", "Description"],
            [
                [
                    opt["name"],
                    opt["type"],
                    "yes" if opt["required"] else "no",
                    str(opt["default"]),
                    opt["description"] or "",
                ]
                for opt in root["global_options"]
            ],
        )
    )
    lines.append("")

    lines.append("## Commands")
    lines.append("")
    lines.extend(
        _md_table(
            ["Command", "Summary"],
            [[f"`{cmd['name']}`", cmd["summary"]] for cmd in root["commands"]],
        )
    )
    lines.append("")

    lines.append("## Environment Variables")
    lines.append("")
    lines.extend(
        _md_table(
            ["Variable", "Required", "Description"],
            [
                [env["name"], "yes" if env["required"] else "no", env["description"]]
                for env in root["environment_variables"]
            ],
        )
    )
    lines.append("")

    lines.append("## Config Files")
    lines.append("")
    lines.append("None." if not root["config_files"] else "\n".join(str(f) for f in root["config_files"]))
    lines.append("")

    lines.append("## Authentication")
    lines.append("")
    lines.append(root["authentication"] or "No authentication required; no API key needed.")
    lines.append("")

    lines.append("## Output Formats")
    lines.append("")
    lines.extend(f"- {fmt}" for fmt in root["output_formats"])
    lines.append("")

    return "\n".join(lines)


def render_command_markdown(command: dict[str, Any]) -> str:
    lines = [
        f"# Command: {command['name']}",
        "",
        "## Summary",
        "",
        command["summary"],
        "",
        "## Description",
        "",
        command["description"],
        "",
        "## Usage",
        "",
        "```bash",
        command["usage"],
        "```",
        "",
    ]

    lines.append("## Arguments")
    lines.append("")
    lines.extend(
        _md_table(
            ["Name", "Type", "Required", "Description"],
            [
                [arg["name"], arg["type"], "yes" if arg["required"] else "no", arg["description"] or ""]
                for arg in command["arguments"]
            ],
        )
    )
    lines.append("")

    lines.append("## Options")
    lines.append("")
    lines.extend(
        _md_table(
            ["Option", "Type", "Required", "Default", "Description"],
            [
                [
                    ", ".join([opt["name"], *opt["aliases"]]),
                    opt["type"],
                    "yes" if opt["required"] else "no",
                    "" if opt["default"] is None else str(opt["default"]),
                    opt["description"] or "",
                ]
                for opt in command["options"]
            ],
        )
    )
    lines.append("")

    lines.append("## Preconditions")
    lines.append("")
    lines.extend(f"- {item}" for item in command["preconditions"])
    lines.append("")

    lines.append("## Effects")
    lines.append("")
    effect_labels = {
        "reads_files": "Reads files",
        "writes_files": "Writes files",
        "uses_network": "Uses network",
        "mutates_local_state": "Mutates local state",
        "mutates_remote_state": "Mutates remote state",
    }
    lines.extend(
        _md_table(
            ["Effect", "Value"],
            [[label, str(command["effects"][key])] for key, label in effect_labels.items()],
        )
    )
    lines.append("")

    lines.append("## Safety")
    lines.append("")
    lines.extend(
        _md_table(
            ["Property", "Value"],
            [[key.replace("_", " ").title(), str(value)] for key, value in command["safety"].items()],
        )
    )
    lines.append("")

    lines.append("## Output")
    lines.append("")
    lines.append(f"Default format: {command['output']['default_format']}")
    lines.append("")
    lines.append("Supported formats:")
    lines.append("")
    lines.extend(f"- {fmt}" for fmt in command["output"]["formats"])
    lines.append("")

    lines.append("## Exit Codes")
    lines.append("")
    lines.extend(
        _md_table(
            ["Code", "Meaning"],
            [[str(entry["code"]), entry["meaning"]] for entry in command["exit_codes"]],
        )
    )
    lines.append("")

    lines.append("## Errors")
    lines.append("")
    lines.extend(
        _md_table(
            ["Code", "Recoverable", "Suggested Action"],
            [
                [entry["code"], "yes" if entry["recoverable"] else "no", entry["suggested_action"] or ""]
                for entry in command["errors"]
            ],
        )
    )
    lines.append("")

    lines.append("## Examples")
    lines.append("")
    for example in command["examples"]:
        lines.append(f"{example['description']}")
        lines.append("")
        lines.append("```bash")
        lines.append(example["command"])
        lines.append("```")
        lines.append("")

    return "\n".join(lines)


def describe(
    command: Annotated[
        str | None, typer.Argument(help="Show details for a single command only.")
    ] = None,
    format: Annotated[
        DescribeFormat, typer.Option("--format", case_sensitive=False, help="Description output format.")
    ] = DescribeFormat.markdown,
) -> None:
    """Show a machine-readable, self-contained description of this CLI and its commands."""
    root = build_root_description()
    if command is not None:
        match = next((c for c in root["commands"] if c["name"] == command), None)
        if match is None:
            raise typer.BadParameter(f"Unknown command {command!r}. Run `dwdweather describe` to list all commands.")
        if format == DescribeFormat.json:
            echo_json(match)
        else:
            typer.echo(render_command_markdown(match))
        return
    if format == DescribeFormat.json:
        echo_json(root)
    else:
        typer.echo(render_root_markdown(root))
