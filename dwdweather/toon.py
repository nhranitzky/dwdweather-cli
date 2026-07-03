"""Fast JSON to TOON v3.0 encoder.

This module intentionally implements an encoder only.  It accepts the JSON data
model as Python values, or JSON text via :func:`from_json`, and emits TOON v3.0.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from collections.abc import Iterable, Mapping, Sequence
from decimal import Decimal
from typing import Any

__all__ = [
    "TOON_VERSION",
    "ToonEncodeError",
    "dump",
    "dumps",
    "from_json",
    "from_json_file",
]

TOON_VERSION = "3.0"

_DELIMITERS = (",", "\t", "|")
_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")
_NUMBER_RE = re.compile(
    r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?$"
)
_RESERVED = {"true", "false", "null"}


class ToonEncodeError(TypeError):
    """Raised when a value cannot be encoded as TOON."""


def dumps(value: Any, *, indent: int = 2, sort_keys: bool = False) -> str:
    """Return *value* encoded as a TOON v3.0 document ending with LF."""

    if not isinstance(indent, int) or indent <= 0:
        raise ValueError("indent must be a positive integer")

    _validate_json_value(value)
    lines: list[str] = []
    encoder = _Encoder(indent=indent, sort_keys=sort_keys)
    encoder.emit_root(value, lines)
    return "\n".join(lines) + "\n"


def dump(value: Any, fp: Any, *, indent: int = 2, sort_keys: bool = False) -> None:
    """Write *value* as TOON to a path-like object or writable text file."""

    text = dumps(value, indent=indent, sort_keys=sort_keys)
    if _is_path_like(fp):
        with open(fp, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    else:
        fp.write(text)


def from_json(text: str, *, indent: int = 2, sort_keys: bool = False) -> str:
    """Parse JSON *text* and return a TOON v3.0 document."""

    return dumps(json.loads(text), indent=indent, sort_keys=sort_keys)


def from_json_file(fp: Any, *, indent: int = 2, sort_keys: bool = False) -> str:
    """Read JSON from a path-like object or readable text file and return TOON."""

    if _is_path_like(fp):
        with open(fp, encoding="utf-8") as f:
            return from_json(f.read(), indent=indent, sort_keys=sort_keys)
    return from_json(fp.read(), indent=indent, sort_keys=sort_keys)


class _Encoder:
    def __init__(self, *, indent: int, sort_keys: bool) -> None:
        self.indent = indent
        self.sort_keys = sort_keys

    def emit_root(self, value: Any, lines: list[str]) -> None:
        if isinstance(value, dict):
            self._emit_object(value, 0, lines)
        elif isinstance(value, list):
            self._emit_array(None, value, 0, lines)
        else:
            lines.append(self._format_primitive(value, ","))

    def _emit_object(self, obj: Mapping[str, Any], depth: int, lines: list[str]) -> None:
        for key, value in self._items(obj):
            self._emit_field(key, value, depth, lines)

    def _emit_field(self, key: str, value: Any, depth: int, lines: list[str]) -> None:
        prefix = self._spaces(depth) + _format_key(key)
        if isinstance(value, dict):
            lines.append(prefix + ":")
            self._emit_object(value, depth + 1, lines)
        elif isinstance(value, list):
            self._emit_array(key, value, depth, lines)
        else:
            lines.append(prefix + ": " + self._format_primitive(value, ","))

    def _emit_array(
        self, key: str | None, arr: Sequence[Any], depth: int, lines: list[str]
    ) -> None:
        tabular = _tabular_shape(arr, self.sort_keys)
        delimiter = self._choose_delimiter_for_array(arr, tabular)
        header = self._array_header(key, len(arr), delimiter, tabular)
        prefix = self._spaces(depth) + header

        if not arr:
            lines.append(prefix)
            return

        if tabular is not None:
            lines.append(prefix)
            fields, rows = tabular
            del fields
            row_prefix = self._spaces(depth + 1)
            for row in rows:
                lines.append(
                    row_prefix
                    + delimiter.join(self._format_primitive(v, delimiter) for v in row)
                )
            return

        if _all_primitives(arr):
            lines.append(
                prefix
                + " "
                + delimiter.join(self._format_primitive(v, delimiter) for v in arr)
            )
            return

        lines.append(prefix)
        for item in arr:
            self._emit_list_item(item, depth + 1, lines)

    def _emit_list_item(self, item: Any, depth: int, lines: list[str]) -> None:
        prefix = self._spaces(depth) + "- "
        if isinstance(item, dict):
            self._emit_object_list_item(item, depth, lines)
        elif isinstance(item, list):
            if _all_primitives(item):
                delimiter = self._choose_delimiter_for_array(item, None)
                values = delimiter.join(
                    self._format_primitive(v, delimiter) for v in item
                )
                sep = " " if item else ""
                lines.append(
                    prefix
                    + self._array_header(None, len(item), delimiter, None)
                    + sep
                    + values
                )
            else:
                lines.append(prefix + self._array_header(None, len(item), ",", None))
                for nested in item:
                    self._emit_list_item(nested, depth + 1, lines)
        else:
            lines.append(prefix + self._format_primitive(item, ","))

    def _emit_object_list_item(
        self, obj: Mapping[str, Any], depth: int, lines: list[str]
    ) -> None:
        items = list(self._items(obj))
        if not items:
            lines.append(self._spaces(depth) + "-")
            return

        first_key, first_value = items[0]
        first_prefix = self._spaces(depth) + "- " + _format_key(first_key)

        if isinstance(first_value, dict):
            lines.append(first_prefix + ":")
            self._emit_object(first_value, depth + 2, lines)
        elif isinstance(first_value, list):
            tabular = _tabular_shape(first_value, self.sort_keys)
            delimiter = self._choose_delimiter_for_array(first_value, tabular)
            header = self._array_header(first_key, len(first_value), delimiter, tabular)
            lines.append(self._spaces(depth) + "- " + header)
            if tabular is not None:
                _, rows = tabular
                for row in rows:
                    lines.append(
                        self._spaces(depth + 2)
                        + delimiter.join(
                            self._format_primitive(v, delimiter) for v in row
                        )
                    )
            elif _all_primitives(first_value):
                if first_value:
                    lines[-1] += " " + delimiter.join(
                        self._format_primitive(v, delimiter) for v in first_value
                    )
            else:
                for nested in first_value:
                    self._emit_list_item(nested, depth + 2, lines)
        else:
            lines.append(first_prefix + ": " + self._format_primitive(first_value, ","))

        for key, value in items[1:]:
            self._emit_field(key, value, depth + 1, lines)

    def _array_header(
        self,
        key: str | None,
        length: int,
        delimiter: str,
        tabular: tuple[Sequence[str], Sequence[Sequence[Any]]] | None,
    ) -> str:
        key_part = "" if key is None else _format_key(key)
        delimiter_part = "" if delimiter == "," else delimiter
        if tabular is None:
            return f"{key_part}[{length}{delimiter_part}]:"
        fields, _ = tabular
        field_part = delimiter.join(_format_key(field) for field in fields)
        return f"{key_part}[{length}{delimiter_part}]{{{field_part}}}:"

    def _choose_delimiter_for_array(
        self,
        arr: Sequence[Any],
        tabular: tuple[Sequence[str], Sequence[Sequence[Any]]] | None,
    ) -> str:
        values: list[Any] = []
        if tabular is None:
            for item in arr:
                if _is_primitive(item):
                    values.append(item)
        else:
            fields, rows = tabular
            values.extend(fields)
            for row in rows:
                values.extend(row)

        best_delimiter = ","
        best_score = None
        for delimiter in _DELIMITERS:
            score = sum(_primitive_quote_cost(value, delimiter) for value in values)
            if best_score is None or score < best_score:
                best_score = score
                best_delimiter = delimiter
        return best_delimiter

    def _format_primitive(self, value: Any, delimiter: str) -> str:
        if value is None:
            return "null"
        if value is True:
            return "true"
        if value is False:
            return "false"
        if isinstance(value, int) and not isinstance(value, bool):
            return str(value)
        if isinstance(value, float):
            return _format_float(value)
        if isinstance(value, str):
            return _format_string(value, delimiter)
        raise ToonEncodeError(f"unsupported value type: {type(value).__name__}")

    def _items(self, obj: Mapping[str, Any]) -> Iterable[tuple[str, Any]]:
        items = obj.items()
        if self.sort_keys:
            return sorted(items)
        return items

    def _spaces(self, depth: int) -> str:
        return " " * (depth * self.indent)


def _format_key(key: str) -> str:
    if _KEY_RE.match(key):
        return key
    return _quote(key)


def _format_string(value: str, delimiter: str) -> str:
    if _is_safe_unquoted_string(value, delimiter):
        return value
    return _quote(value)


def _quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _is_safe_unquoted_string(value: str, delimiter: str) -> bool:
    if value == "" or value != value.strip():
        return False
    if value in _RESERVED or _NUMBER_RE.match(value):
        return False
    if delimiter in value:
        return False
    if "\n" in value or "\r" in value or "\t" in value:
        return False
    if any(ord(ch) < 0x20 for ch in value):
        return False
    if ":" in value or '"' in value or "[" in value or "]" in value:
        return False
    if "{" in value or "}" in value:
        return False
    if value == "-" or value.startswith("- "):
        return False
    return True


def _format_float(value: float) -> str:
    if not math.isfinite(value):
        raise ToonEncodeError("non-finite floats are not JSON-compatible")
    if value == 0:
        return "0"
    decimal = Decimal(repr(value)).normalize()
    text = format(decimal, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text == "-0" else text


def _validate_json_value(value: Any) -> None:
    if value is None or isinstance(value, str):
        return
    if isinstance(value, bool):
        return
    if isinstance(value, int):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ToonEncodeError("non-finite floats are not JSON-compatible")
        return
    if isinstance(value, list):
        for item in value:
            _validate_json_value(item)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ToonEncodeError("object keys must be strings")
            _validate_json_value(item)
        return
    raise ToonEncodeError(f"unsupported value type: {type(value).__name__}")


def _tabular_shape(
    arr: Sequence[Any], sort_keys: bool
) -> tuple[Sequence[str], Sequence[Sequence[Any]]] | None:
    if not arr or not all(isinstance(item, dict) and item for item in arr):
        return None

    first = arr[0]
    fields = sorted(first.keys()) if sort_keys else list(first.keys())
    rows: list[list[Any]] = []
    for item in arr:
        keys = sorted(item.keys()) if sort_keys else list(item.keys())
        if keys != fields:
            return None
        row = [item[key] for key in fields]
        if not all(_is_primitive(value) for value in row):
            return None
        rows.append(row)
    return fields, rows


def _all_primitives(values: Sequence[Any]) -> bool:
    return all(_is_primitive(value) for value in values)


def _is_primitive(value: Any) -> bool:
    return (
        value is None
        or isinstance(value, str)
        or isinstance(value, bool)
        or (isinstance(value, int) and not isinstance(value, bool))
        or isinstance(value, float)
    )


def _primitive_quote_cost(value: Any, delimiter: str) -> int:
    if isinstance(value, str) and not _is_safe_unquoted_string(value, delimiter):
        return len(_quote(value)) - len(value)
    return 0


def _is_path_like(value: Any) -> bool:
    return isinstance(value, (str, bytes, os.PathLike))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert JSON to TOON v3.0.")
    parser.add_argument("input", nargs="?", help="JSON input file. Reads stdin if omitted.")
    parser.add_argument("-o", "--output", help="TOON output file. Writes stdout if omitted.")
    parser.add_argument("--indent", type=int, default=2, help="spaces per indentation level")
    parser.add_argument("--sort-keys", action="store_true", help="sort object keys")
    parser.add_argument("--version", action="version", version=f"TOON encoder {TOON_VERSION}")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.input:
            text = from_json_file(args.input, indent=args.indent, sort_keys=args.sort_keys)
        else:
            text = from_json(sys.stdin.read(), indent=args.indent, sort_keys=args.sort_keys)

        if args.output:
            with open(args.output, "w", encoding="utf-8", newline="\n") as fp:
                fp.write(text)
        else:
            sys.stdout.write(text)
        return 0
    except (OSError, json.JSONDecodeError, ToonEncodeError, ValueError) as exc:
        parser.exit(1, f"toon: error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
