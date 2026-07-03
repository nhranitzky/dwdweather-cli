# Pitfall: Don't introspect Typer's command tree via `isinstance` against the `click` package

Typer's internal Click coupling is not stable across versions. This matters for any feature that walks `typer.main.get_command(app)` to inspect commands, arguments, and options — most notably a `describe`/self-description implementation.

## The trap

It's tempting to introspect the Click objects Typer builds like this:

```python
import click

if isinstance(param, click.Argument): ...
if isinstance(param.type, click.Choice): ...
if isinstance(command, click.Group): ...
ctx = click.Context(command, info_name="mycli sub")
```

This works with some Typer versions and silently breaks with others.

## Why it breaks

Some Typer releases vendor their own internal copy of Click (e.g. `typer._click`, an independent fork, not a re-export of the standalone `click` package — verified via its own docstring: *"Code taken and adapted from Click..."*). When that's the case, Typer's `TyperArgument`/`TyperOption`/`TyperCommand`/`TyperGroup` inherit from the **vendored** classes, not from the external `click` package's classes.

`isinstance` checks against the external `click` package then return `False` for every parameter — **not an ImportError, not a crash, just silently empty or wrong introspection results** (e.g. a `describe` command reporting zero arguments/options for every command). This is much harder to catch than a hard failure, since the CLI still runs and produces *some* JSON, just structurally incomplete.

Declaring `click` as an explicit dependency does **not** fix this — the package is present either way; the problem is which class hierarchy Typer's runtime objects actually belong to, and that has changed between Typer releases.

## The fix

Duck-type against Click's small, stable attribute surface instead of importing `click` and checking `isinstance`. These attributes are present and named identically regardless of which Click implementation Typer uses underneath, because any Typer-compatible fork has to preserve them to stay drop-in compatible with Click's own internals (help rendering, shell completion, etc.):

| Instead of | Use |
|---|---|
| `isinstance(p, click.Argument)` | `getattr(p, "param_type_name", None) == "argument"` |
| `isinstance(p, click.Option)` | `getattr(p, "param_type_name", None) == "option"` |
| `isinstance(t, click.Choice)` | `hasattr(t, "choices")` |
| `isinstance(t, click.types.IntRange \| FloatRange)` | `hasattr(t, "min") and hasattr(t, "max")` |
| `isinstance(t, click.types.BoolParamType)` etc. | `getattr(t, "name", "")` (Click's own type-name string, e.g. `"boolean"`, `"integer"`, `"integer range"`, `"float"`, `"choice"`) |
| `isinstance(cmd, click.Group)` | `hasattr(cmd, "commands")` |
| `click.Context(command, info_name=...)` | `command.context_class(command, info_name=...)` — lets the Command supply its own compatible Context class instead of hardcoding one |

Type-hint the introspected objects as `Any` rather than `click.Argument`/`click.Option`/`click.Command` — the point of this pattern is precisely that the concrete implementation is not something the code should depend on.

## Testing implication

A test suite that only mocks the CLI's own business logic (geocoding, HTTP calls, etc.) will not catch this — it needs at least one test that actually walks the real, live command tree (e.g. `describe --format json` against the real Typer app) and asserts that arguments/options are non-empty and correctly typed, so that a Typer upgrade which changes this internal coupling is caught by CI rather than shipped silently.
