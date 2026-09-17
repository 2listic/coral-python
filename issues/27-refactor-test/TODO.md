# TODO — open problems after issue #27

Everything in [`plan.md`](plan.md) is implemented. This file is what is **left**, written to be
picked up cold.

State: branch `27-refactor-test`, PR #29 open. 586 tests — 582 in the fast lane (~0.9s), 585 offline
(33s, the phiflow simulation); the wheel acceptance test needs the internet.

## Open

### 1. `test_tuple_return` is a poor node-type name

`plugins/coral-math/src/coral_plugin_math/__init__.py:132` declares a node type starting with
`test_`, so pytest collects the callable behind it as a test and errors on a missing fixture. Worked
around by an aliased import at `plugins/coral-math/tests/unit/test_functions.py:25`.

**Done looks like** renaming the node type — platform-facing, since a graph naming it would break,
hence deferred.

### 2. phiflow annotates 23 of its 48 slots `Any`

Graph check 8 skips an edge it cannot judge, so a grid wired where a float belongs fails 30 seconds
into the simulation instead of at t=0. Math and string are at zero `Any`; the builtins' 9 are
deliberate and not fixable.

**Done looks like** precise annotations in `coral_plugin_phiflow`. A plugin change, belonging to
whoever owns the plugin. It is also most of why phiflow sits at 70% coverage.

### 3. Nothing stops `uv.lock` picking up unrelated upgrades

A `uv sync` run while `[tool.uv.workspace] members` was stale re-resolved the lock and silently
upgraded jax 0.10.2 → 0.11.0. It was caught by reading the diff; nothing in the repo would have
objected.

*Decided:* recorded as a review habit under **Package Management** in `CLAUDE.md`. `uv lock --check`
does not answer this question — the lock was internally consistent afterwards. A real check needs CI,
which does not exist (issue #21).

### 4. A plugin's four names differ three ways

Directory `plugins/coral-math`, distribution `coral-plugin-math`, import package
`coral_plugin_math`, entry point `math`. **No action, as designed** — the alternatives and their
costs are in `plan.md` under *Rejected alternatives*. Here so nobody re-derives it.

## Closed since this file was written

| | how |
| --- | --- |
| the source-root list was duplicated three ways, one copy guarded | `TestConfigCoversEveryDistribution` parses `pytest.ini` and `pyproject.toml` |
| a plugin named `fake` would have broken the build | the host's bogus literal is now `not-a-real-plugin`, and the namespace constraint is stated in `tests/README.md` |
| `definitions/` was left empty | removed |
| a plugin declaring a function and a class under one name went unreported | `nodeports.build_port_table` raises `DuplicateNodeTypeError` |
| the test categories were described by symptom, not by rule | audit of 2026-09-03 — category 1 restated as *installation independence*; `coral-core/tests/` and `test_plugin_present.py` given categories; three guards added; `tests/README.md` cut to a decision table |
