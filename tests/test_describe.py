from __future__ import annotations

import json

from typer.testing import CliRunner

from dwdweather.cli import app
from dwdweather.errors import KNOWN_ERRORS

runner = CliRunner()

ROOT_REQUIRED_FIELDS = [
    "schema_version",
    "kind",
    "name",
    "version",
    "summary",
    "description",
    "global_options",
    "commands",
    "environment_variables",
    "config_files",
    "authentication",
    "output_formats",
]

COMMAND_REQUIRED_FIELDS = [
    "name",
    "summary",
    "description",
    "usage",
    "arguments",
    "options",
    "examples",
    "preconditions",
    "effects",
    "safety",
    "output",
    "exit_codes",
    "errors",
    "idempotent",
    "mutates_state",
    "requires_network",
    "supports_dry_run",
]

PARAM_REQUIRED_FIELDS = [
    "name",
    "aliases",
    "type",
    "required",
    "default",
    "enum",
    "description",
    "examples",
    "sensitive",
    "deprecated",
    "hidden",
]

ROOT_MARKDOWN_SECTIONS = [
    "## Description",
    "## Global Options",
    "## Commands",
    "## Environment Variables",
    "## Config Files",
    "## Authentication",
    "## Output Formats",
]

COMMAND_MARKDOWN_SECTIONS = [
    "## Summary",
    "## Description",
    "## Usage",
    "## Arguments",
    "## Options",
    "## Preconditions",
    "## Effects",
    "## Safety",
    "## Output",
    "## Exit Codes",
    "## Errors",
    "## Examples",
]


def _root_json() -> dict:
    result = runner.invoke(app, ["describe", "--format", "json"])
    assert result.exit_code == 0
    return json.loads(result.stdout)


def test_describe_default_format_is_markdown() -> None:
    result = runner.invoke(app, ["describe"])
    assert result.exit_code == 0
    assert result.stdout.startswith("# dwdweather")


def test_describe_json_is_valid_and_has_root_fields() -> None:
    root = _root_json()
    for field in ROOT_REQUIRED_FIELDS:
        assert field in root, f"missing root field {field!r}"
    assert root["kind"] == "cli.describe"
    assert root["name"] == "dwdweather"
    assert root["output_formats"] == ["text", "json", "toon"]


def test_describe_lists_all_six_commands_and_excludes_itself() -> None:
    root = _root_json()
    names = [command["name"] for command in root["commands"]]
    assert names == ["alerts", "current", "forecast", "history", "stations", "summary"]
    assert "describe" not in names


def test_describe_environment_variables_include_tz() -> None:
    root = _root_json()
    names = [env["name"] for env in root["environment_variables"]]
    assert "DWDWEATHER_TZ" in names


def test_describe_command_json_has_required_fields() -> None:
    result = runner.invoke(app, ["describe", "history", "--format", "json"])
    assert result.exit_code == 0
    command = json.loads(result.stdout)
    for field in COMMAND_REQUIRED_FIELDS:
        assert field in command, f"missing command field {field!r}"
    assert command["name"] == "history"
    assert command["requires_network"] is True
    assert command["supports_dry_run"] is False


def test_describe_every_command_has_examples() -> None:
    root = _root_json()
    for command in root["commands"]:
        assert command["examples"], f"{command['name']} has no examples"


def test_describe_arguments_and_options_have_required_fields() -> None:
    root = _root_json()
    history = next(c for c in root["commands"] if c["name"] == "history")
    for arg in history["arguments"]:
        for field in PARAM_REQUIRED_FIELDS:
            assert field in arg, f"missing argument field {field!r}"
    for option in history["options"]:
        for field in PARAM_REQUIRED_FIELDS:
            assert field in option, f"missing option field {field!r}"
    date_option = next(o for o in history["options"] if o["name"] == "--date")
    assert date_option["required"] is True
    limit_option = next(o for o in history["options"] if o["name"] == "--limit")
    assert limit_option["type"] == "integer"
    assert limit_option["default"] == 8784
    output_option = next(o for o in history["options"] if o["name"] == "--output")
    assert output_option["enum"] == ["text", "json", "toon"]


def test_describe_unknown_command_exits_2() -> None:
    result = runner.invoke(app, ["describe", "does-not-exist"])
    assert result.exit_code == 2
    assert "dwdweather describe" in result.output


def test_describe_root_markdown_has_required_sections() -> None:
    result = runner.invoke(app, ["describe"])
    for section in ROOT_MARKDOWN_SECTIONS:
        assert section in result.stdout, f"missing section {section!r}"


def test_describe_command_markdown_has_required_sections() -> None:
    result = runner.invoke(app, ["describe", "current"])
    assert result.exit_code == 0
    assert result.stdout.startswith("# Command: current")
    for section in COMMAND_MARKDOWN_SECTIONS:
        assert section in result.stdout, f"missing section {section!r}"


def test_describe_errors_catalog_matches_known_errors() -> None:
    root = _root_json()
    for command in root["commands"]:
        codes = {entry["code"] for entry in command["errors"]}
        assert codes == set(KNOWN_ERRORS.keys())
        for entry in command["errors"]:
            expected = KNOWN_ERRORS[entry["code"]]
            assert entry["message"] == expected["message"]
            assert entry["exit_code"] == expected["exit_code"]
            assert entry["recoverable"] == expected["recoverable"]
            assert entry["suggested_action"] == expected["suggested_action"]
