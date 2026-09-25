# The test suite

Every test lives in the package it is about. This directory holds only what belongs to no package.

## Where does my test go?

Answer in order; the first **yes** wins.

| ask | category | write it in |
| --- | --- | --- |
| One plugin `<n>`, and you can make the claim by calling that plugin's own Python? | 3 plugin unit | `plugins/coral-<n>/tests/unit/` |
| One plugin `<n>`, but you need `coral_app` — a graph, its registry slice? | 4 plugin system | `plugins/coral-<n>/tests/system/` |
| The app, or the `Plugin` ABC, naming no plugin? | 2 framework | `coral-app/tests/`, `coral-core/tests/` |
| The repo as a whole — its source text, its packaging? | 1 repo-level | `tests/` |

Then:

- **Needs two plugin names?** It is a host rule, not a plugin fact. Rewrite it on the specimen,
  `coral-app/tests/specimen.py`, and file it under 2.
- **Brings a graph, an example or a golden?** It ships in the same package as the test that reads it.
- **Docstrings** are GIVEN / WHEN / THEN, one clause per line, blank line before the assertions.

## What each category may touch

| # | where | may import | may name a plugin | skips? |
| --- | --- | --- | --- | --- |
| 1 | `tests/` | anything but a plugin | as **data** only | only `discovery/`, when nothing is installed |
| 2 | `coral-core/tests/`, `coral-app/tests/` | `coral_core`, `coral_app` | **never** | never |
| 3 | `plugins/coral-<n>/tests/unit/` | `coral_plugin_<n>`, `coral_core` | `<n>` only | whole dir, if `<n>` absent |
| 4 | `plugins/coral-<n>/tests/system/` | the above **+ `coral_app`** | `<n>` only | whole dir, if `<n>` absent |

Category 2 runs against a designed specimen, never a real plugin — that is what makes the host
agnostic rather than merely claiming to be. Category 1 may *name* a plugin as data
(`test_acceptance.py` pip-installs `coral-plugin-math` into a throwaway venv) but never import one.

`tests/invariants/test_source_rules.py` enforces all of the above by reading the source, and names
the offending file. One consequence: it compares string literals for equality, so **a new plugin
must not be named after a literal in the framework suites** — you would get a failure pointing at a
file with nothing wrong in it. Rename the literal, never the rule.

## Running it

```bash
pytest                                  # everything
pytest -m "not slow"                    # the fast lane, ~0.9s
pytest -m "not network"                 # offline
pytest plugins/coral-math/tests/unit    # selection is by path, not by marker
```

| marker | means | carried by |
| --- | --- | --- |
| `slow` | costs real time | the phiflow simulation (~33s), the wheel acceptance test |
| `network` | needs the internet | the wheel acceptance test only |

Two cost rules: **no unmarked test may run a simulation** — exactly one does and it is `slow`, every
other phiflow graph is validated without executing — and **a test that runs something asserts a
value**.

## What must not weaken

| pinned | by | how |
| --- | --- | --- |
| `node_types.json`, format | `coral-app/tests/golden/node_types.format.json` | bytes, from the specimen |
| `node_types.json`, content | `plugins/coral-<n>/tests/system/golden/` | bytes, per plugin |
| graph JSON | each owner's `test_graphs_validate.py` | every shipped graph constructs a `Graph` |

The graphs are real editor exports. Do not hand-author one and call it a format guard.

## Subset installs

A plugin's `tests/` survives `uv pip uninstall`: its `conftest.py` drops every module that would
import the plugin, and `unit/test_plugin_present.py` stays to report a named skip. `coral-app/tests`
and `tests/` pass with **zero** plugins installed and **zero** skips — re-check that after touching
either.

Reasoning and mechanics: `CLAUDE.md`. History: `issues/27-refactor-test/`.
