# The test suite

There is no single test directory. Every test lives in the package it is about, and this directory
holds only what belongs to no package in particular.

That is one rule, not a filing convention, and it is the whole content of issue #27. What follows is
the rule, where each kind of test goes, and how to run what you want.

## The separation principle

Every test belongs to exactly one of three kinds, and the directory it sits in says which:

| # | kind | where | plugin names it may use | skips? |
| --- | --- | --- | --- | --- |
| 1 | **host** — the app itself, on a designed specimen | `coral-app/tests/` | **none** | never |
| 2 | **plugin unit** — a plugin's own functions and classes | `plugins/coral-<n>/tests/unit/` | `<n>` | whole dir, if `<n>` is absent |
| 3 | **plugin system** — that plugin's graphs through `coral_app` | `plugins/coral-<n>/tests/system/` | `<n>` | whole dir, if `<n>` is absent |

Plus this directory, which keeps only what needs **no plugin name at all** and scans the package
directories from disk.

**The rule that decides every case:**

> A test that needs one plugin's name belongs to that plugin. A test that needs *two* is testing a
> host rule, not a plugin fact — rewrite it on the specimen plugins and give it to the host.

The old suite sorted tests by what they *imported*, which is an accident of how each was written. It
produced ~38 `@pytest.mark.<plugin>` markers on tests of the *host*, an auto-skip hook to keep them
green on a subset install, and a shared `tests/fixtures/` directory of graphs with no owner. All three
are gone.

**Data ships with its owner.** A graph, an example or a golden lives in the package whose tests read
it — so a graph's plugin requirement *is* its directory, never something a test works out at run time.
That is what removed the last table mapping example directories to the plugins they need.

## What is here

```
tests/
├── conftest.py                       # one fixture: project_root
├── invariants/
│   └── test_source_rules.py          # rules about the source *text*, read from disk
├── discovery/
│   └── test_installed_plugins.py     # the entry-point contract, against real distributions
└── test_acceptance.py                # wheels built and pip-installed into a clean venv
                                      #   (`slow` + `network` — the only test needing the internet)
```

Nothing here imports a plugin or names one. `invariants` and `test_acceptance` derive the plugin set
from `plugins/coral-*` on disk; `discovery` derives it from `discover()`.

**`invariants/test_source_rules.py`** fails when *someone wrote a forbidden line* — the fix is always
to change that line. Four families:

| forbidden in | what |
| --- | --- |
| every package's `src` | `from __future__ import annotations` (it would collapse every registry socket to `any`) |
| `coral-app/src` | any `coral_plugin_*` import |
| `plugins/coral-*/src` | any `coral_app` import |
| `coral-app/tests` | a `coral_plugin_*` import, a `mark.<plugin>`, or a string literal equal to a plugin name |

That last row is the separation principle made executable: it is what stops the host suite drifting
back to being written against whichever plugin was handy. Allowed deliberately: a plugin's own name
inside its own tests, and `coral_app` inside a plugin's `tests/system/`.

The same file also holds the stage boundaries from issue #23 — `graph.py` never imports `inspect`,
`executor.py` never imports `json` or `graphlib`.

**`discovery/test_installed_plugins.py`** covers what needs a real installed distribution: that
`discover()` matches entry-point metadata, that importing is lazy (checked in a subprocess, since this
session has already imported things), that every installed plugin's nodes appear, and that the
installed set is usable *together* — no two of them claiming one node type. It skips cleanly on a bare
install, which is correct: there is no distribution to make a claim about.

The host's own side of that contract — fail-loud on an unknown name, the zero-plugin host, the merge,
the duplicate-name refusal — is in `coral-app/tests/test_discovery.py`, against the specimen,
where it runs with nothing installed and never skips.

## Where everything else lives

```
coral-core/tests/                      # the Plugin ABC enforces both methods. Nothing else.

coral-app/
├── examples/collections/             # `coral run .../list.json` — the host's own demos
└── tests/
    ├── specimen.py                   # the designed plugin surface + 5 plugins (see below)
    ├── host_suite.py                 # paths, importable at collection time
    ├── conftest.py                   # specimen_plugins, isolate_cwd, write_graph
    ├── graphs/                       # the pure-collection graphs
    ├── golden/node_types.format.json # the file *format*, byte-compared
    ├── test_nodeports.py             # stage 2: describing a callable
    ├── test_graph.py                 # stage 3: all seven checks
    ├── test_executor.py              # stage 4: on the specimen
    ├── test_registry.py              # stage 5: format, port numbering, key order
    ├── test_builtin_nodes.py         # the host's list/set/dict functions
    ├── test_discovery.py             # the host's side of the plugin contract
    ├── test_graphs_validate.py       # its graphs construct; none executes
    └── test_examples.py              # its examples run, with plugins=[]

plugins/coral-<n>/tests/               # per plugin: <n>_suite.py, conftest.py,
                                       #   test_plugin_present.py, graphs/, unit/, system/
```

### The specimen

The host suite runs against `coral-app/tests/specimen.py`: functions and classes written only
for testing, chosen so that between them they exhibit every shape the host must describe and execute —
a zero-input function, a multi-output one, a `None`-returning one, an unannotated one, an explicit
`Any`, a dotted function name, a class with methods, an unrelated class, a subclass.

Five `Plugin` subclasses expose it, and the split is driven by the host's merge rules alone:
`SpecimenPlugin` (the whole surface), `RivalPlugin` (a second, non-colliding peer, so ordering can be
pinned), and `FunctionClashPlugin` / `ClassClashPlugin` / `BuiltinClashPlugin`, each of which exists
only to be **refused** with `DuplicateNodeTypeError`.

They are not a distribution. The suite hands them to the host by patching the one lookup that maps a
plugin *name* to an instance (`coral_app.load`); everything downstream of it — the merge, the port
table, the registry, graph validation, execution — is production code.

## Running it

```bash
pytest                     # everything
pytest -m "not slow"       # the fast lane: ~0.8s
pytest -m "not network"    # the offline lane: everything but the wheel acceptance test
pytest -m slow             # the one fluid simulation, and the wheel acceptance test
```

Two markers, both about **cost**, and they are independent rather than a partition — `slow` is *costs
real time*, `network` is *needs the internet*:

| | `slow` | `network` |
| --- | --- | --- |
| `plugins/coral-phiflow/tests/system/test_graphs_run.py` (the simulation, ~33s) | yes | — |
| `tests/test_acceptance.py` (wheels into a clean venv) | yes | yes |

The acceptance test carries both on purpose. It is 4s with a warm uv cache but ~250s when PyPI has
published a jax the workspace does not pin — `uv pip install` resolves fresh and never reads
`uv.lock` — and `_run()` captures output, so that run prints nothing and looks hung. Dropping `slow`
from it would let the fast lane collect it, which would give the ~0.8s lane a network dependency; that
is why it is marked twice rather than moved.

Selection is **by path**, because a test's subject is its directory:

```bash
pytest coral-app/tests                    # the host
pytest plugins/coral-math/tests/unit      # math's callables — no host, no graph
pytest plugins/coral-phiflow/tests/system # phiflow's graphs through the host
pytest tests                              # only what names no plugin
```

### The two cost rules

- **No unmarked test may run a simulation.** Exactly one test runs PhiFlow's solver
  (`plugins/coral-phiflow/tests/system/test_graphs_run.py`, `slow`, ~33s). Every other phiflow
  graph is *validated without being executed*: constructing a `Graph` runs all seven checks and calls
  nothing, so the graph-JSON contract is guarded at ~0 ms per file instead of up to 32.76s.
- **A test that runs something asserts a value.** Several graphs used to be executed by tests whose
  only assertion was `isinstance(results, dict)` — wall-clock with no failure mode. Those graphs now
  assert their arithmetic, in their owner's `test_graphs_run.py`.

### Subset installs

A plugin's `tests/` directory survives `uv pip uninstall`, so it guards itself: its `conftest.py` reads
its own entry point and drops `unit/` and `system/` from collection when absent — they cannot be
imported without the plugin — while `test_plugin_present.py` imports nothing from it and survives to
report the skip.

```bash
uv pip uninstall coral-plugin-phiflow && uv run --no-sync pytest -m "not slow"
uv sync   # restore
```

With **all three** plugins uninstalled, `coral-app/tests` and `tests/` pass with **zero
skips**. That is the property that makes the host agnostic rather than merely claiming to be, and it is
worth re-checking after touching either.

## The two contracts

Both artefacts the DealiiX platform exchanges with us are pinned, and neither guard may be weakened:

| shape | guarded by | how |
| --- | --- | --- |
| `node_types.json` — format | `coral-app/tests/golden/node_types.format.json` | bytes, from the specimen plugins |
| `node_types.json` — content | each plugin's `tests/system/golden/node_types.<n>.json` | bytes, per plugin |
| graph JSON | each owner's `test_graphs_validate.py` | every shipped graph constructs a `Graph` |

The registry golden was split by owner deliberately: renaming a format key should produce one diff in
the host's golden, not force edits in three plugin packages before anyone can see what changed. Every
replacement is a byte comparison of a fixed plugin set, which is *stricter* than the single all-plugins
golden it replaced — that one had to be compared by parsed content, because its ordering depended on
which plugins happened to be installed.

The graph exports are ground truth: they are what the editor actually produces. Do not hand-author a
graph and call it a format guard, and do not edit an export except as a recorded, deliberate act
(issue #27 renamed one node type in three of them, and says so).

## Writing a test here

Docstrings are **GIVEN / WHEN / THEN**, one clause per line:

```python
def test_a_zero_input_function_runs(self, run):
    """GIVEN a function taking no inputs at all
    WHEN it is executed
    THEN it is called and its result stored — no edge is needed to trigger it."""
```

Then a blank line before the assertions, so the arrangement and the claim stay visually separate. Where
a test exists for a reason its name cannot carry — an otherwise unreachable branch, a value only
checkable at run time, a number that must only ever go down — say so in a paragraph under the THEN.
Several tests here are the only thing that can reach the code they cover, and that is worth writing
down rather than rediscovering.
