# CLI Review: Selbstbeschreibung (`describe`) — Delta-Review

Fokus dieses Reviews: die Vorgabe zur Selbstbeschreibung im `llmcli`-Skill hat sich geändert. Vorher (siehe `documents/review.md`, Befund war dort nicht vorhanden, da noch nicht Teil der Prinzipien): *"For very complex CLIs, expose machine-readable command discovery via `commands list --output json`, `schema`, or `capabilities`"* — optional, Namensfreiheit. Jetzt (`cli-design-principles.md`): *"Expose machine-readable command discovery via a `describe` subcommand by default — this is a standard part of every CLI built with this skill, unless the user explicitly opts out."* Verbindliches Format ist in `cli-describe-spec.md` spezifiziert.

Dieses Dokument prüft ausschließlich die Selbstbeschreibungs-Fähigkeit gegen `cli-describe-spec.md` und den entsprechenden Abschnitt in `cli-python.md` ("Implementation Guidance for Python Typer"). Alle übrigen, bereits in `documents/review.md` behandelten Punkte sind nicht Teil dieses Reviews und wurden umgesetzt.

Geprüfter Stand: `dwdweather/commands/discovery.py`, `dwdweather/cli.py`, `dwdweather/render.py` (`render_commands`), `tests/test_cli.py` (`test_commands_list_*`).

## Zusammenfassung

Der bestehende `dwdweather commands list`-Befehl wurde vor Inkrafttreten der neuen `describe`-Spezifikation gebaut (als Antwort auf die damals noch optionale "machine-readable command discovery"-Empfehlung). Er liefert bereits einen funktionierenden Introspektions-Mechanismus auf Basis der echten Click-Kommandostruktur (eine einzige Metadatenquelle, kein manuell gepflegtes Duplikat) — das ist die richtige Grundarchitektur und sollte wiederverwendet, nicht verworfen werden. Er erfüllt jedoch weder den geforderten Befehlsnamen (`describe` statt `commands list`), noch das geforderte Ausgabeformat (`markdown` fehlt komplett), noch den geforderten Metadatenumfang (der Großteil der in `cli-describe-spec.md` verlangten Felder fehlt). Zwei parallele, unterschiedlich geformte Discovery-Mechanismen (`commands list` und ein künftiges `describe`) nebeneinander zu betreiben, würde selbst gegen das in der Spec verankerte "Single Source"-Prinzip verstoßen — `commands list` sollte daher zu `describe` umgebaut bzw. davon abgelöst werden, nicht ergänzt werden.

## Befunde

### Blocker

1. **Kein `describe`-Befehl vorhanden.**
   Die Spezifikation verlangt zwingend `<cli> describe`, `<cli> describe --format markdown|json`, `<cli> describe <command>` und `<cli> describe <command> --format markdown|json`. Implementiert ist stattdessen `dwdweather commands list --output text|json|toon` — anderer Befehlsname (`commands list` statt `describe`), anderer Flag-Name (`--output` statt `--format`), andere Werte (`text|json|toon` statt `markdown|json`), und kein Sub-Argument für einen einzelnen Befehl (`describe <command>`).
   *Fix:* Neuen Befehl `describe` implementieren (siehe Vorschlag unten), der intern dieselbe Introspektions-Engine wie `discovery.py` nutzt. `commands list` danach entfernen, um keine zwei divergierenden Discovery-Ausgaben zu pflegen (Single-Source-Prinzip der Spec).

   <comment> Entferne commands, und implementiere describe</command>

2. **Kein `markdown`-Ausgabeformat.**
   `markdown` muss laut Spec das *Default*-Format von `describe` sein. Das CLI kennt aktuell nur `text`, `json`, `toon` (`OutputFormat` in `commands/common.py`) — `describe` benötigt ein eigenes `--format markdown|json`-Flag (nicht das bestehende `--output`, da dessen Wertemenge und Zweck ein anderer ist: `--output` steuert die Darstellung der *Wetterdaten*, `--format` bei `describe` steuert die Darstellung der *Selbstbeschreibung*).
   *Fix:* In `discovery.py` (bzw. dem neuen `describe.py`) einen eigenen `DescribeFormat`-Enum (`markdown`, `json`) mit `--format`-Option einführen, unabhängig von `OutputFormat`. Markdown-Rendering gemäß dem in `cli-describe-spec.md` vorgegebenen Abschnittsschema (`# <cli>`, `## Description`, `## Global Options`, `## Commands`, `## Environment Variables`, `## Config Files`, `## Authentication`, `## Output Formats` auf Root-Ebene; `# Command: <name>` mit den dort gelisteten Unterabschnitten auf Befehlsebene).

  <comment> implementiere describe mit Markdown</command>

3. **Keine `--describe`-Aliase.**
   Die Spec verlangt (wo technisch machbar) zusätzlich `<cli> --describe` und `<cli> <command> --describe` als Kurzformen. Aktuell existiert kein globales `--describe`-Flag auf dem Root-Callback und kein `--describe`-Flag auf den einzelnen Subcommands.
   *Fix:* Auf dem Root-`@app.callback()` ein eager `--describe`-Flag ergänzen (analog zu `--version`), das die Root-`describe`-Ausgabe im Default-Format (`markdown`) druckt und beendet. Pro Subcommand ein `--describe`-Flag zu ergänzen ist optional laut Spec ("where technically feasible") — bei sechs Wetter-Befehlen mit identischer `OutputOption`-Struktur vertretbarer Zusatzaufwand, aber niedrigere Priorität als Punkt 1–2.

  <comment> Kein --describe implementieren</command>

### Warnungen

4. **Root-Metadaten fehlen vollständig.**
   Die Spec verlangt auf CLI-Ebene mindestens: `schema_version`, `kind` (`"cli.describe"`), `name`, `version`, `summary`, `description`, `global_options`, `commands`, `environment_variables`, `config_files`, `authentication`, `output_formats`. `commands list` liefert nur `{"meta": {...}, "data": {"commands": [...]}}` — keines der Root-Felder aus der Spec ist vorhanden, insbesondere fehlen `environment_variables` (obwohl `DWDWEATHER_TZ` real existiert, siehe `--tz`-Option in allen Wetterbefehlen) und `config_files`/`authentication` (die explizit mit `null`/leer beantwortet werden könnten, da dieses CLI keine Config-Datei und keine Authentifizierung hat — aber auch das muss laut Spec *explizit* ausgewiesen werden, nicht implizit durch Abwesenheit).
   *Fix:* Root-`describe`-Objekt gemäß Minimal-Root-Struktur aus der Spec bauen; `version` aus `dwdweather.__version__`, `environment_variables` mit `DWDWEATHER_TZ` (required: false, description, default: "Europe/Berlin"), `config_files: []` (es gibt keine Config-Datei, nur den Cache unter `platformdirs.user_cache_dir`), `authentication: null` (kein API-Key nötig).

  <comment> mplementieren</command>

5. **Command-Metadaten decken nur einen kleinen Teil der geforderten Felder ab.**
   `_command_schema()` liefert aktuell `name`, `help`, `arguments`, `options`. Laut Spec fehlen pro Befehl: `summary` (Kurzfassung, getrennt von `description`), `usage` (kanonischer Aufrufstring, z. B. `dwdweather current LOCATION... [--tz TZ] [--output text|json|toon]` — bereits im README vorhanden, aber nicht maschinenlesbar verfügbar), `examples`, `preconditions`, `effects` (`reads_files`/`writes_files`/`uses_network`/`mutates_local_state`/`mutates_remote_state`), `safety` (`risk_level`/`destructive`/`requires_confirmation`), `output` (`default_format`/`formats`/`json_schema`), `exit_codes`, `errors` (maschinenlesbare Fehlerliste – `DwdWeatherError`-Codes existieren bereits in `errors.py`/`api.py`/`geocode.py`, sind aber nirgends zentral aufgelistet), `idempotent`, `mutates_state`, `requires_network`, `supports_dry_run`.
   *Fix:* Da alle sechs Wetterbefehle rein lesend sind, sind die meisten dieser Felder trivial und für alle Befehle identisch zu befüllen: `effects.uses_network: true`, `effects.mutates_local_state: true` (Geocoding-Cache-Datei wird geschrieben, siehe `cache.py`), alle anderen `effects`/`mutates_state` auf `false`, `idempotent: true`, `requires_network: true`, `supports_dry_run: false` (keine schreibenden/destruktiven Operationen vorhanden, daher irrelevant), `safety.risk_level: "low"`, `safety.destructive: false`. `exit_codes` und `errors` lassen sich aus dem bereits dokumentierten Exit-Code-Schema (`dwdweather/README.md`, Abschnitt "Exit Codes") sowie den `DwdWeatherError`-Codes (`NO_DATA`, `LOCATION_NOT_FOUND`, `RATE_LIMITED`, `NETWORK_ERROR`, `SERVICE_UNAVAILABLE`, `API_ERROR`, `GEOCODING_ERROR`) ableiten und sollten dort als eine gemeinsame, importierbare Konstante gepflegt werden, damit README und `describe`-Ausgabe nicht auseinanderlaufen (Single-Source-Prinzip).

  <comment> Implementieren</command>

6. **Kein `describe <command>` für einzelne Befehle.**
   Die Spec verlangt explizit die Möglichkeit, einen einzelnen Befehl gezielt zu beschreiben (`<cli> describe <command>`), nicht nur die Gesamtliste. `commands list` kennt kein Argument zur Filterung auf einen Befehl.
   *Fix:* `describe` als eigene Typer-Gruppe mit optionalem Positional-Argument implementieren: `dwdweather describe [COMMAND] [--format markdown|json]`. Ohne Argument → Root-Beschreibung inkl. aller Befehle; mit Argument → nur das einzelne Befehlsschema (bei unbekanntem Namen: Fehler mit Exit-Code 2 und Vorschlag `dwdweather describe` zur Übersicht, konsistent mit dem bestehenden `suggestion`-Feld-Muster in `errors.py`).

  <comment> Implementieren</command>

7. **Options-/Argument-Metadaten sind unvollständig gegenüber der Spec.**
   `_option_schema()`/`_argument_schema()` liefern `name`/`flags`, `type`, `required`, `default`, `help`, optional `envvar`/`choices`/`min`/`max`. Es fehlen `aliases` (Kurzflags gibt es zwar aktuell keine mehr im CLI, aber das Feld sollte laut Schema trotzdem vorhanden sein, z. B. als leere Liste), `enum` (aktuell nur implizit über `choices` bei `--output` abgedeckt, aber nicht unter dem von der Spec verlangten Feldnamen `enum`), `examples`, `sensitive` (bei diesem CLI immer `false`, da keine Secrets übergeben werden, aber explizit anzugeben), `deprecated`, `hidden`.
   *Fix:* Schema-Funktionen um die fehlenden Felder ergänzen; bei diesem CLI sind die meisten Werte statisch (`sensitive: false`, `deprecated: false`, `hidden: false`), nur `examples` erfordert je Option eine kurze manuelle Ergänzung (z. B. `--tz`: `["Europe/Berlin", "UTC"]`, `--days`: `[3, 7]`).

  <comment> Implementieren</command>

### Vorschläge

8. **Keine Tests für die Selbstbeschreibung nach neuem Schema (`test_describe.py`).**
   `cli-python.md` verlangt ein eigenes `test_describe.py` mit Prüfungen, dass `describe --format json` valides JSON liefert, das JSON dem erwarteten Schema entspricht, Markdown alle Pflichtabschnitte enthält, jeder Befehl in der Root-Beschreibung auftaucht, jeder Befehl Beispiele hat, jeder zustandsverändernde Befehl Safety-Metadaten trägt, jeder destruktive Befehl als `high`-Risk markiert ist, und jeder Befehl mit strukturierten Daten `--output json` unterstützt (hier bereits erfüllt). Die bestehenden `test_commands_list_*`-Tests in `tests/test_cli.py` prüfen nur die alte, unvollständige Struktur.
   *Fix:* `tests/test_describe.py` anlegen; bestehende `test_commands_list_*`-Tests entfernen/migrieren, sobald `commands list` durch `describe` ersetzt ist.

  <comment> Implementieren</command>

9. **Fehler- und Exit-Code-Katalog existiert nur verstreut in Prosa/Code, nicht als importierbare Struktur.**
   Für `errors`/`exit_codes` in der `describe`-Ausgabe braucht es eine zentrale, maschinenlesbare Quelle. Aktuell sind Exit-Codes nur in `dwdweather/README.md` als Tabelle dokumentiert, und Fehlercodes ergeben sich implizit aus den `raise DwdWeatherError(...)`-Aufrufen in `api.py`, `geocode.py` und den Command-Modulen — es gibt keine zentrale Liste.
   *Fix:* Eine kleine Konstante (z. B. `KNOWN_ERRORS` in `errors.py`) mit `{code, message_template, exit_code, recoverable, suggested_action}` je Fehlerklasse einführen; sowohl `describe` als auch (optional, zukünftig) das README daraus generieren bzw. dagegen validieren.

     <comment> Implementieren</command>


10. **`--tz`/`DWDWEATHER_TZ` ist die einzige Umgebungsvariable, aber nirgends maschinenlesbar deklariert.**
    Für `environment_variables` in der Root-Beschreibung muss diese Variable strukturiert (Name, `required: false`, Default, Beschreibung) auftauchen. Aktuell nur in Prosa im README erwähnt.
    *Fix:* Sobald Root-Metadaten (Befund 4) implementiert sind, `DWDWEATHER_TZ` dort eintragen.

     <comment> Fixen</command>

## Abgleich mit der "Minimal Acceptance Checklist" aus `cli-describe-spec.md`

| Kriterium | Status |
|---|---|
| Exposes a `describe` command | ❌ nicht vorhanden (nur `commands list`) |
| Can output Markdown | ❌ fehlt |
| Can output valid JSON | ✅ (`commands list --output json`, muss aber ins `describe`-Schema migriert werden) |
| Describes all commands | ✅ (alle 6 Wetterbefehle, `commands` selbst wird bewusst ausgeschlossen) |
| Describes arguments/options mit type/default/required | ⚠️ teilweise (Basisfelder vorhanden, `enum`/`aliases`/`sensitive`/`deprecated`/`hidden` fehlen) |
| Includes examples | ❌ fehlt vollständig (weder pro Befehl noch pro Option) |
| Describes outputs and exit codes | ❌ fehlt (`output.json_schema`, `exit_codes` nicht vorhanden) |
| Marks side effects and risks | ❌ fehlt (`effects`, `safety`, `mutates_state`, `requires_network`, `idempotent`, `supports_dry_run`) |
| Uses a single metadata source | ✅ Grundprinzip bereits korrekt umgesetzt (Click-Introspektion statt Duplikat) — muss bei der Migration erhalten bleiben |
| Has tests for the description output | ⚠️ teilweise (Tests existieren, aber für das alte, unvollständige Schema) |

**Fazit:** 2 von 10 Kriterien erfüllt, 2 teilweise, 6 nicht erfüllt. Die vorhandene Introspektions-Basis (`discovery.py`) ist eine gute Grundlage und sollte zu `describe.py` weiterentwickelt statt neu geschrieben werden.
