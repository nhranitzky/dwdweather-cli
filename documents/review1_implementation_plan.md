# Implementation Plan: `describe`-Selbstbeschreibung

Basiert auf `documents/review1.md` und den Kommentaren dazu. Ersetzt den bestehenden `commands list`-Mechanismus vollständig durch einen spezifikationskonformen `describe`-Befehl (`cli-describe-spec.md`).

Status: **umgesetzt** (siehe Checklist). `ruff`/`mypy --strict`/`pytest` grün (88 Tests), Gesamt-Coverage 91 % (`describe.py`: 99 %). Alle 10 Kriterien der „Minimal Acceptance Checklist“ aus `cli-describe-spec.md` erfüllt — `--describe`-Alias bewusst ausgelassen (Befund 3, per Kommentar).

## Entscheidungen (aus den Kommentaren und dem Interview)

- **`commands list` entfernen, `describe` neu implementieren** (Befund 1). Kein Parallelbetrieb zweier Discovery-Mechanismen.
- **Markdown-Rendering implementieren** (Befund 2), eigenes `DescribeFormat`-Enum unabhängig von `OutputFormat`.
- **Kein `--describe`-Alias** (Befund 3) — weder global noch pro Subcommand. Nur der `describe`-Befehl selbst.
- **Root-Metadaten implementieren** (Befund 4): `schema_version`, `kind`, `name`, `version`, `summary`, `description`, `global_options`, `commands`, `environment_variables`, `config_files`, `authentication`, `output_formats`.
- **Vollständige Command-Metadaten implementieren** (Befund 5): `summary`, `usage`, `examples`, `preconditions`, `effects`, `safety`, `output`, `exit_codes`, `errors`, `idempotent`, `mutates_state`, `requires_network`, `supports_dry_run`.
- **`describe <command>` implementieren** (Befund 6): optionales Positional-Argument für Einzelabfrage.
- **Options-/Argument-Metadaten vervollständigen** (Befund 7): `aliases`, `enum`, `examples`, `sensitive`, `deprecated`, `hidden`.
- **`tests/test_describe.py` anlegen** (Befund 8), alte `test_commands_list_*`-Tests entfernen.
- **Zentraler Fehlerkatalog `KNOWN_ERRORS`** (Befund 9) in `errors.py`, ein Eintrag pro Fehlercode (nicht pro Command), `message` als repräsentativer Text, `suggested_action` aus den bestehenden `suggestion`-Werten übernommen.
- **`DWDWEATHER_TZ` in `environment_variables`** (Befund 10), sobald Root-Metadaten existieren.
- **`--format`-Werte:** nur `markdown`/`json` (nicht `toon`), strikt nach Spec.
- **Default-Format:** `markdown`, unabhängig von TTY-Erkennung (Spec verlangt das unconditional, anders als `--output` bei den Wetterbefehlen).
- **Unbekannter Befehlsname bei `describe <command>`:** `typer.BadParameter` → Exit-Code 2, mit Hinweistext auf `dwdweather describe`.
- **Fehlerkatalog-Ort/-Form:** ein globaler `KNOWN_ERRORS`-Katalog in `errors.py`; da alle sechs Wetterbefehle über `resolve_location`/`brightsky_get` denselben Satz an Fehlercodes auslösen können (`NO_DATA`, `LOCATION_NOT_FOUND`, `RATE_LIMITED`, `NETWORK_ERROR`, `SERVICE_UNAVAILABLE`, `API_ERROR`, `GEOCODING_ERROR`), wird dieselbe `errors`-Liste für jeden Command wiederverwendet — kein Pflegeaufwand pro Command.
- **`effects`/`safety`/`idempotent`/`mutates_state`/`requires_network`/`supports_dry_run` sind für alle sechs Wetterbefehle identisch** (rein lesende Operationen, aber mit lokalem Geocoding-Cache-Schreibzugriff): `reads_files: false`, `writes_files: true`, `uses_network: true`, `mutates_local_state: true`, `mutates_remote_state: false`, `safety.risk_level: "low"`, `safety.destructive: false`, `safety.requires_confirmation: false`, `idempotent: true`, `mutates_state: true`, `requires_network: true`, `supports_dry_run: false`.
- **`usage`-String wird aus Click selbst erzeugt** (`command.get_usage(ctx)`), nicht manuell dupliziert — bleibt damit Single-Source.
- **`json_schema` pro Command:** flaches, handgeschriebenes JSON-Schema-Dict (`meta`/`location`/`data` auf oberster Ebene, `data` nur grob typisiert) — kein Pydantic, konsistent mit der bereits im ursprünglichen Review dokumentierten, bewussten Pydantic-Abstinenz von `spec.md`.
- **`exit_codes`** als globale, für alle Commands identische Liste (deckt sich mit der bestehenden Tabelle in `dwdweather/README.md`).

## Checklist

### 1. Zentrale Kataloge in `errors.py`
- [x] `KNOWN_ERRORS: dict[str, dict[str, Any]]` ergänzen: ein Eintrag je Code (`NO_DATA`, `LOCATION_NOT_FOUND`, `RATE_LIMITED`, `NETWORK_ERROR`, `SERVICE_UNAVAILABLE`, `API_ERROR`, `GEOCODING_ERROR`) mit `message`, `exit_code`, `recoverable`, `suggested_action`.
- [x] `EXIT_CODES: list[dict[str, Any]]` ergänzen (0–4, Text aus `dwdweather/README.md` „Exit Codes“ übernehmen).

### 2. `describe.py` anlegen (ersetzt `discovery.py`)
- [x] Neue Datei `dwdweather/commands/describe.py`; Introspektions-Helfer aus `discovery.py` übernehmen (`_type_name`, `_argument_schema`, `_option_schema`) und erweitern:
  - [x] `_argument_schema`: `aliases: []`, `enum: null`, `examples: []`, `sensitive: false`, `deprecated: false`, `hidden: false` ergänzen.
  - [x] `_option_schema`: dieselben Zusatzfelder; `enum` = `choices` falls `click.Choice`, sonst `null`; `aliases` = alle `opts` außer dem primären Flag.
- [x] `_command_schema()` erweitern um `summary`, `usage` (via `command.get_usage(ctx)`), `examples`, `preconditions`, `effects`, `safety`, `output` (inkl. `json_schema`), `exit_codes` (aus `EXIT_CODES`), `errors` (aus `KNOWN_ERRORS`), `idempotent`, `mutates_state`, `requires_network`, `supports_dry_run`.
- [x] Je Command ein `examples`-Eintrag (mind. 1, realistisch, `safe: true`) hart hinterlegen (kurze, manuell gepflegte Liste — z. B. `dwdweather current Berlin`, `dwdweather forecast Berlin --days 3`, `dwdweather history Berlin --date 2026-01-01`, `dwdweather alerts Berlin`, `dwdweather stations Berlin --radius 50`, `dwdweather summary Berlin`).
- [x] `build_root_description() -> dict[str, Any]`: `schema_version="1.0"`, `kind="cli.describe"`, `name="dwdweather"`, `version=dwdweather.__version__`, `summary`/`description` aus der App-Hilfe, `global_options` (aus dem Root-Callback: `--debug`, `--version`), `commands` (Liste aller Command-Schemas), `environment_variables` (`DWDWEATHER_TZ`), `config_files: []`, `authentication: null`, `output_formats: ["text", "json", "toon"]`.
- [x] `DescribeFormat(StrEnum)`: `markdown`, `json`; Default `markdown` (kein TTY-Bezug).
- [x] `describe(command: str | None = None, format: DescribeFormat = DescribeFormat.markdown) -> None`:
  - [x] Ohne `command`: Root-Beschreibung ausgeben (JSON via `echo_json(root)` bzw. Markdown via `render_root_markdown(root)`).
  - [x] Mit `command`: passendes Command-Schema suchen; wenn nicht gefunden → `typer.BadParameter(f"Unknown command {command!r}. Run \`dwdweather describe\` to list all commands.")` (Exit-Code 2); sonst Einzel-Schema ausgeben (JSON flach, kein `meta`/`data`-Envelope — deckt sich mit dem Root-JSON, das ebenfalls flach ist).
- [x] `render_root_markdown(root)`: Abschnitte exakt nach Spec-Vorlage (`# dwdweather`, `## Description`, `## Global Options`, `## Commands`, `## Environment Variables`, `## Config Files`, `## Authentication`, `## Output Formats`).
- [x] `render_command_markdown(command)`: Abschnitte exakt nach Spec-Vorlage (`# Command: <name>`, `## Summary`, `## Description`, `## Usage`, `## Arguments`, `## Options`, `## Preconditions`, `## Effects`, `## Safety`, `## Output`, `## Exit Codes`, `## Errors`, `## Examples`).
- [x] `dwdweather/commands/discovery.py` löschen.

### 3. `render.py` aufräumen
- [x] `render_commands()` und den zugehörigen `_flag_summary()`-Helfer entfernen (nicht mehr genutzt, da `describe`-Rendering in `describe.py` lebt, nicht in `render.py` — deckt sich mit dem Modul-Layout aus `cli-python.md`).

### 4. `cli.py` verdrahten
- [x] Import `discovery` → `describe` ersetzen.
- [x] `app.add_typer(discovery.commands_app, name="commands")` entfernen.
- [x] `app.command("describe")(describe.describe)` ergänzen.

### 5. Dokumentation
- [x] `dwdweather/README.md`: Abschnitt „`commands list`“ durch „`describe`“ ersetzen; Command-Overview-Block aktualisieren (`dwdweather describe [COMMAND] [--format markdown|json]`); Beispielausgabe (Markdown-Ausschnitt) ergänzen.
- [x] Root-`README.md`: falls dort `commands list` erwähnt wird, ebenfalls anpassen (aktuell nicht der Fall, zur Sicherheit prüfen).

### 6. Tests
- [x] `tests/test_cli.py`: alle `test_commands_list_*`-Tests entfernen.
- [x] Neue Datei `tests/test_describe.py`:
  - [x] `describe` ohne Argumente/Flags liefert Markdown (Default), beginnt mit `# dwdweather`.
  - [x] `describe --format json` liefert valides JSON mit allen Root-Pflichtfeldern (`schema_version`, `kind`, `name`, `version`, `summary`, `description`, `global_options`, `commands`, `environment_variables`, `config_files`, `authentication`, `output_formats`).
  - [x] Alle sechs Wetterbefehle tauchen in `commands` auf; `describe` selbst nicht (Selbstausschluss wie bisher bei `commands list`).
  - [x] `describe history --format json` liefert nur das Einzel-Schema von `history` mit allen Pflichtfeldern (`summary`, `usage`, `arguments`, `options`, `examples`, `preconditions`, `effects`, `safety`, `output`, `exit_codes`, `errors`, `idempotent`, `mutates_state`, `requires_network`, `supports_dry_run`).
  - [x] Jeder Command hat mindestens ein Beispiel (`examples` nicht leer).
  - [x] `describe <unbekannt>` exitet mit Code 2 und nennt `dwdweather describe` als Hinweis.
  - [x] Root-Markdown enthält alle Pflichtabschnitte (`## Description`, `## Global Options`, `## Commands`, `## Environment Variables`, `## Config Files`, `## Authentication`, `## Output Formats`).
  - [x] Command-Markdown (`describe current`) enthält alle Pflichtabschnitte (`## Summary`, `## Description`, `## Usage`, `## Arguments`, `## Options`, `## Preconditions`, `## Effects`, `## Safety`, `## Output`, `## Exit Codes`, `## Errors`, `## Examples`).
  - [x] Optionen enthalten `aliases`/`enum`/`examples`/`sensitive`/`deprecated`/`hidden`.
  - [x] `errors`-Liste je Command stimmt mit `KNOWN_ERRORS` aus `errors.py` überein (Cross-Check, verhindert Drift).
- [x] `tests/test_units.py`: ggf. Unit-Test für `KNOWN_ERRORS`/`EXIT_CODES`-Konsistenz (z. B. jeder in `errors.py` tatsächlich geworfene Code ist auch in `KNOWN_ERRORS` vorhanden).

### 7. Abschluss
- [x] `uv run ruff check dwdweather tests`, `uv run mypy dwdweather`, `uv run pytest tests/` grün.
- [x] Coverage-Regression prüfen (`uv run --with pytest-cov --with coverage pytest tests/ --cov=dwdweather --cov-report=term-missing`), Ziel weiterhin ≥ 80 %.
- [x] Manuell verifizieren: `dwdweather describe` (Markdown), `dwdweather describe --format json`, `dwdweather describe history --format json`, `dwdweather describe nichtvorhanden` (Exit-Code 2), `dwdweather --help` zeigt `describe` statt `commands`.
- [x] Abgleich mit der „Minimal Acceptance Checklist“ aus `cli-describe-spec.md` erneut durchführen — Ziel: alle 10 Kriterien erfüllt (außer ggf. bewusst ausgelassenes `--describe`, siehe Befund 3).
