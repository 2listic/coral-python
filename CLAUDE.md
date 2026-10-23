# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Coral for Python** is a workflow execution system that processes computational graphs defined in JSON format. The system supports four types of nodes:
- **Primitive nodes**: Hold constant values (int, float, string, bool, any)
- **Function nodes**: Execute Python functions with typed inputs and outputs
- **Constructor nodes**: Instantiate Python classes
- **Method nodes**: Call instance methods on objects created by constructor nodes

A registered class may instead be **abstract**: its key types sockets and appears in `bases` /
`derived`, but it offers no constructor node (see `abstract=` under Core components).

The four kinds are unchanged by where a node comes from, but note that not every node comes from a
plugin: besides the primitives, the host ships **function** nodes of its own — the collection
operations in `coral_app/builtin_nodes.py`, available with no plugin installed at all. See
[Built-in collection nodes](#built-in-collection-nodes).

The project uses PhiFlow for physics simulations and numerical computing.

The repo is a **uv workspace / monorepo**: a small set of independently installable distributions —
the framework at the root (`coral-core/`, `coral-app/`) and one directory per plugin under `plugins/`.
A minimal contract package (`coral-core`) defines `Plugin`, on which a plugin declares its node
types with decorators; the host (`coral-app`) discovers and loads plugins at runtime via
`importlib.metadata` entry points; each capability (`math`, `string`, `phiflow`, `pypde`) is its own
`coral-plugin-*` distribution. See
[Package layout](#package-layout) below.

> For the narrative — goals, architecture rationale, the two contracts with the DealiiX platform, and how to
> extend the project — see [`docs/ONBOARDING.md`](docs/ONBOARDING.md). This
> `CLAUDE.md` is the mechanics reference; `README.md` covers setup and commands.

## Development Commands

### Environment Setup

This is a uv **workspace** (virtual root `pyproject.toml` + `uv.lock`); the per-package
`pyproject.toml` files + `uv.lock` are the source of truth for dependencies.

```bash
# Create .venv and install every workspace package editable (incl. the dev group) from the lockfile
uv sync

# Then activate, or prefix commands with `uv run` (e.g. `uv run coral run`)
source .venv/bin/activate  # Linux/Mac
```

`uv sync` installs every workspace package **editable**, plugins included — entry-point discovery finds
them from the checkout, so development never uses `pip` and never installs a plugin separately.

### Code Quality

A pre-commit hook runs `ruff format` and `ruff check` on staged Python files; both read
`[tool.ruff]` in the root `pyproject.toml` (pinned rule set `E4/E7/E9/F/I`, 100 columns, Markdown
excluded). Install it once per clone with `uv run pre-commit install`. A third hook runs the fast
test lane (`pytest -m "not slow"`, ~1.5s) on every commit, whatever is staged; it excludes the fluid
simulation and the wheel acceptance test, which is also what keeps the hook offline.

```bash
uv run pre-commit run --all-files   # everything the hook would do, over the whole repo
uv run ruff format coral-core coral-app plugins tests
uv run ruff check coral-core coral-app plugins tests
```

### Package Management
```bash
# Add a runtime dependency to a specific workspace package (updates its pyproject.toml + uv.lock)
uv add --package coral-plugin-phiflow <package-name>

# Add a dev-only dependency (to the workspace root dev group)
uv add --dev <package-name>

# Re-resolve the lockfile and sync the environment
uv lock && uv sync
```

**Read the `uv.lock` diff before committing it.** Nothing enforces this, and one specific accident is
why it is written down (issue #27, step 9): a `uv sync` run while `[tool.uv.workspace] members` was
stale — it pointed at a directory that no longer existed, and a **memberless workspace is valid**, so
the command succeeded. It uninstalled all five packages, re-resolved from scratch, and silently
upgraded `jax` 0.10.2 → 0.11.0 along with `jaxlib` and `matplotlib`. Reading the diff is what caught it.

Two habits follow, and neither is checkable by a tool:

- **Never run `uv sync` after moving a package directory without updating `members` first.** The
  failure is silent in both directions: uv accepts a workspace that matches nothing, and the upgrade
  it performs looks like an unrelated commit's noise. (The invariants suite now fails on a stale root —
  `TestConfigCoversEveryDistribution` in `tests/invariants/test_source_rules.py` — but only once tests
  run, i.e. after the re-resolve has already happened.)
- **A `uv.lock` diff should touch only what you meant to change.** After a package move that is
  exactly the `editable = { path = ... }` strings and nothing else; after a `uv add` it is that
  dependency and its transitive closure. Any other version bump in the diff is an accident until
  proven deliberate.

`uv lock --check` does *not* answer this question — it verifies the lock is consistent with the
manifests, and after that accidental re-resolve it was perfectly consistent.

### Distribution (wheels)

The wheel is the boundary between the two audiences: this repo's workflow is uv-only, end users are
pip-only. Build one wheel per package into `dist/` and ship that directory:

```bash
uv build --all-packages --wheel --out-dir dist
```

End users then `pip install --find-links dist coral-app` (plus any `coral-plugin-*`) without uv — see
Installation in `README.md`. Building is a distribution step, not part of the development loop.

### Running Workflows

`coral` is a coral-compatible CLI (the `coral-app` console script, `coral_app.cli:main`): a global
`-p/--plugin` option (comma-separated plugin names; empty = all installed) plus `register` / `run`
/ `plugins` subcommands. `-p/--plugin` must precede the subcommand.
```bash
# Run a workflow graph (graph path required; all installed plugins by default)
coral run path/to/workflow.json
coral -p "math" run path/to/workflow.json
coral -p "phiflow" run plugins/coral-phiflow/examples/phiflow/smoke_plume_2D.json

# Send the per-node status markers somewhere other than the cwd
coral run path/to/workflow.json --touch-dir /run/job-42

# Generate the node registry (writes node_types.json into the cwd)
coral register
coral -p "math" register
coral register --output="custom-registry.json"

# List the installed plugins, one name per line (what -p accepts)
coral plugins
```

The `coral-py` launcher wraps this for the DealiiX platform: it runs the `coral` console script inside the uv
workspace (`exec uv run --quiet --project "$HERE" coral "$@"`) while preserving the caller's cwd (so `register`
writes `node_types.json` there). Point the platform's `coralBinaryPath` at `coral-py` and set `coralPluginPath`
to the plugin list.

**Default plugin behavior**: When `-p/--plugin` is omitted, all installed plugins are loaded (via entry-point
discovery, in `sorted(discover())` order). Primitives are always included. An unknown / not-discoverable `-p`
name, or a name given twice, is refused by the CLI before any subcommand runs — `parser.error`, exit
status 2, every offending name at once plus the installed ones — so `run` has not yet touched its
`--touch-dir`. Below the CLI, `load()` still raises `LookupError` for an unknown name.

**Available plugins** (each an installed `coral-plugin-*` distribution, registered under the `coral.plugins`
entry-point group):
- `math` - Mathematical operations, Calculator class and a Shape hierarchy with multiple inheritance
- `string` - StringProcessor class
- `phiflow` - PhiFlow physics simulation wrappers
- `pypde` - py-pde PDE-solver wrappers

### Running Tests

```bash
# The whole suite: the repo-level tests plus every package's own (from the workspace root)
pytest

# The fast lane — everything except the one fluid simulation and the wheel build (~0.8s)
pytest -m "not slow"

# The offline lane — everything except the one test that downloads from PyPI
pytest -m "not network"

# With coverage over every package's src
pytest --cov --cov-report=html && open htmlcov/index.html
```

**Selection is by path, not by marker** (issue #27, R3). A test lives in the package it is about, so
naming a directory is how you name a subject:

```bash
pytest coral-app/tests                    # the host, on its designed specimen
pytest plugins/coral-math/tests           # the math plugin: its own functions and its graphs
pytest plugins/coral-math/tests/unit      # just its callables — no host, no graph
pytest plugins/coral-phiflow/tests/system # its graphs through the host
pytest tests                              # only what needs no plugin installed
pytest coral-app/tests/test_graph.py::TestEdgeTypes  # a class, as usual
```

Two markers survive, both about **cost** rather than about which plugin a test needs. They are
independent properties, not a partition, so one test carries both:

- `slow` — *costs real time*: the three simulations — phiflow's (~33s) and pypde's diffusion (~12s)
  and obstacles (~8s) — and the wheel acceptance test. Everything else is the fast lane.
- `network` — *needs the internet*: `tests/test_acceptance.py` only, which pip-installs wheels into a
  clean venv. It is 4s with a warm uv cache, but **~250s** whenever PyPI has published a `jax` newer
  than the workspace's pin — `uv pip install` resolves fresh and never reads `uv.lock`, so the cache
  misses and it downloads jax+jaxlib. Its `_run()` captures output, so such a run prints nothing and
  looks hung; it is not.

The acceptance test is marked twice deliberately: dropping `slow` from it would let the fast lane
collect it, giving the ~0.8s lane a network dependency.

**The layout, and the rule that decides it** — every test belongs to exactly one of four kinds, and
the directory says which (see [`tests/README.md`](tests/README.md) for the full statement):

| kind | where | plugin names it may use |
| --- | --- | --- |
| repo-level | `tests/` | as **data** only, never imported; needs none installed |
| framework | `coral-core/tests/`, `coral-app/tests/` | **none**; never skips |
| plugin unit | `plugins/coral-<n>/tests/unit/` | `<n>` |
| plugin system | `plugins/coral-<n>/tests/system/` | `<n>` |

> A test that needs one plugin's name belongs to that plugin. A test that needs *two* is testing a
> host rule, not a plugin fact — rewrite it on the specimen plugins and give it to the host.

That rule decides between the last three. The repo-level kind is decided by a different property —
it must pass with **zero** plugins installed — so it may name one as data (`test_acceptance.py`
pip-installs `coral-plugin-math` into a throwaway venv) but may never import one.

Data ships with its owner: a graph, example or golden lives in the package whose tests use it, so a
graph's plugin requirement is its directory and never something inferred at run time.

**Two rules worth knowing before adding a test:**

- **No unmarked test may run a simulation.** Exactly one test per solver does: phiflow's, and pypde's
  diffusion and obstacles, each in its own package's `tests/system/test_graphs_run.py`, all marked
  `slow`. A solve without time stepping is not a simulation: pypde's Poisson graph runs unmarked. Every other
  simulation graph is *validated without being executed* — constructing a `Graph` runs all eleven
  checks and calls nothing, so the graph-JSON contract is guarded at ~0 ms per file.
- **The framework suites name no plugin.** `coral-app/tests/specimen.py` provides a designed
  plugin surface (`specimen_plugin`, `rival_plugin`, and five clash plugins that exist to be refused),
  handed to the host by patching the one name→instance lookup. Enforced from outside by
  `tests/invariants/test_source_rules.py`, which fails on a `coral_plugin_*` import, a `mark.<plugin>`,
  or a string literal equal to a plugin name anywhere under `coral-core/tests` or `coral-app/tests`.

**Subset installs.** Each plugin's `tests/` guards itself: its `conftest.py` reads its own entry point
and, when absent, drops from collection everything that cannot be imported without the plugin —
`system/` entire, and every module in `unit/` but `test_plugin_present.py`, which survives to report
the skip. So a subset install yields named skips, never errors:

```bash
uv pip uninstall coral-plugin-phiflow && uv run --no-sync pytest -m "not slow"
uv sync   # restore
```

`coral-app/tests` and `tests/` are the exception: they name no plugin, so with **every**
plugin uninstalled they pass with zero skips — which is the property that makes the host agnostic
rather than merely claiming to be.

## Architecture

### Package layout

The layout says which part is open and which is not: the framework sits at the root, and every
extension is a directory under `plugins/`. Adding a plugin is routine; touching the host is not.

```
pyproject.toml                     # virtual uv workspace root (no [project]); members + sources
coral-core/                        # the contract: Plugin, its decorators and declarations. Depends on nothing internal.
└── src/coral_core/__init__.py
coral-app/                         # the host: discovery, node types, graph, executor, CLI. Depends on coral-core only.
└── src/coral_app/
    ├── __init__.py                # PLUGIN_GROUP, discover/load, build_function_map/build_class_map
    ├── primitives.py              # the primitive node types (PRIMITIVES_MAP) + how each reads its value
    ├── builtin_nodes.py           # the host's own functions: the list/set/dict operations
    ├── nodeports.py               # the port table: each node type's inputs and outputs
    ├── graph.py                   # read, validate and order a workflow graph
    ├── registry.py                # node_types.json generation (renders the port table)
    ├── executor.py                # graph execution: walk the order, call each node
    ├── nodestatus.py              # the per-node status markers: qualified ids + the marker files
    └── cli.py                     # register / run subcommands; console script `coral`
plugins/                           # the open set: a third-party plugin is a peer of these four
├── coral-math/                    # entry point `math`  -> coral_plugin_math:plugin
├── coral-string/                  # entry point `string`-> coral_plugin_string:plugin
├── coral-phiflow/                 # entry point `phiflow` -> coral_plugin_phiflow:plugin (owns phiflow/jax/h5py)
└── coral-pypde/                   # entry point `pypde` -> coral_plugin_pypde:plugin (owns py-pde/h5py)
```

**A plugin has four names, and only the directory drops the word `plugin`** — worth knowing before
grepping for one:

| | value |
| --- | --- |
| directory | `plugins/coral-math` |
| distribution (what `pip install` names) | `coral-plugin-math` |
| import package | `coral_plugin_math` |
| entry point (what `-p` selects) | `math` |

**Dependency direction (strict):** `coral-core` depends on nothing internal; `coral-app` depends on `coral-core`;
each plugin depends on `coral-core` **and only core** (never on `coral-app`); the host never imports a plugin —
it finds them at runtime via entry-point discovery.

### Core components

1. **`coral-core`** — the shared contract. A plugin is an **instance** of the concrete class
   `Plugin`; its node types are declared on it with three decorators, each usable bare, with
   options, or as a plain call on an object defined elsewhere, and each returning its target
   unchanged:
   ```python
   plugin = Plugin()

   @plugin.function                       # node "add"
   def add(a: float, b: float) -> float: ...

   @plugin.cls                            # node "Calculator" (its constructor)
   class Calculator:
       @plugin.method(const=True, outputs="value")    # node "Calculator.get_value"
       def get_value(self) -> float: ...

   plugin.function(math.atan2, name="math.atan2",
                   annotations={"y": float, "x": float, "return": float})
   ```
   There is no `name`/`describe` — a plugin's **entry-point name** is its identity. The options are
   `name=` (the node name; default `__name__`; a class's or method's may not contain `.`),
   `inputs=` (`{parameter: label}`), `outputs=` (output names in port order; not on `cls`) and
   `annotations=` (types for the parameters, and `"return"` except on `cls`, the signature leaves
   unannotated). These four
   are **labels only**: wiring stays positional. Every option is kept in the plugin, never on the
   target.
   What can be checked without a signature is checked at the decorator: the target's kind (`function`
   takes any non-class callable, `cls` a class, `method` a plain function other than `__init__` /
   `__new__`), the options' shapes, and duplicates within the plugin (a name used twice across
   functions and classes, a class or method declared twice; one function under two names is an alias).
   `cls` refuses a `typing.Protocol`: its subclasses are decided by structure, a registered class's
   bases by inheritance.

   `plugin.cls` takes one more option, `abstract=`, which is not a label: an **abstract** class
   only types sockets (its key, `bases` / `derived`) and has no constructor node. Omitted, it is
   `inspect.isabstract(cls)`; `abstract=True` always wins; `abstract=False` on a class with
   unimplemented abstract methods raises, as do `inputs=` / `annotations=` on an abstract class
   (they describe a constructor it does not have). Its declared methods are still nodes, run on a
   concrete subclass's instance.

   **What a node modifies** is declared too, and it is not a label either. A method is taken to
   modify its instance unless declared `const=True`; a function or method modifies none of its other
   parameters unless it names them with `writes=` (a name or a sequence; not on `cls`, since a
   constructor modifies none of its inputs). A modified input is a **pass-through**: its port is an
   output too, so a graph can order every node reading the value before the one modifying it (see
   [Graph validation](#graph-validation)). What is not declared is not checked: that a node modifies
   nothing it does not declare, and that its outputs, or the state a constructed instance keeps,
   share no mutable object with a read input (a node keeping or returning one copies it), are the
   author's contract, like an annotation. The host's collection builtins keep it for the
   collection, not for its elements: they copy shallowly. Two outputs of a node may not hold one
   object when a writer reads one of them: the executor refuses that, and two outputs sharing a
   part of one object are again the author's to avoid.

   **Methods are opt-in**: only a declared method is a node. `plugin.functions()` /
   `plugin.classes()` resolve the declarations when the host asks, so declaration order does not
   matter: for each declared class the MRO is walked, and an attribute is a method node when some
   class in it holds a function this plugin declared under that attribute. A subclass therefore has
   its bases' declared methods (registered or not); an undeclared override keeps the node and its
   `name=` / `inputs=` / `outputs=` / `writes=` / `const=`, but cannot keep `annotations=`, which
   describe one function's signature: when the declaration has them, the override must be declared
   itself. **An override may promise more than what it overrides, never less**, compared with every
   declared function under that attribute in the MRO, not only the nearest: an override of a
   `const` method must itself be declared `const=True`, and a declared override may not write a
   parameter a base reads, compared by position, since an override may rename it.
   Declarations are not inherited across plugins. `classes()` raises if a declared method belongs to
   no registered class, if two of a class's methods resolve to one node name, or if an override is
   not a function, replaces a method declared with `annotations=` without a declaration of its own,
   or promises less than a method it overrides.

   What the host receives are frozen dataclasses: `functions()` -> `{node type: Declaration(target,
   inputs, outputs, annotations, writes)}`, `classes()` -> `{class key: ClassDeclaration(target,
   inputs, annotations, methods, abstract)}`, `methods` being `{method node type:
   MethodDeclaration(attribute, declaration, const)}` keyed by the full `<class key>.<name>`.
   `coral_core` builds no port; that is the host's job. The one signature it reads is to compare an
   override's written parameters with its bases', by position.

2. **Plugins (`coral-plugin-*`)** — each module creates `plugin = Plugin()` and declares its node
   types on it. Each declares itself under the `coral.plugins` entry-point group with that
   **instance** as the target, e.g. `[project.entry-points."coral.plugins"] math = "coral_plugin_math:plugin"`.
   The entry-point **name** (`math` / `string` / `phiflow` / `pypde`) is the identity the platform's `-p` contract uses and
   must not change. `coral-plugin-phiflow` declares `phiflow`/`jax`/`h5py` as hard dependencies.

3. **`coral-app`** — the host. Its `__init__.py` provides:
   - `PLUGIN_GROUP = "coral.plugins"`.
   - `discover() -> list[str]`: lists installed plugin names, **sorted**, **without importing** any.
   - `load(name) -> Plugin`: imports **only** that plugin and returns the `Plugin` instance its entry
     point resolves to (`TypeError` for anything else, a `Plugin` subclass included); unknown name →
     `LookupError`.
   - `build_function_map(include=None, exclude=None)` / `build_class_map(...)`: merge the selected
     plugins' `functions()` / `classes()` declarations, re-backed by `discover`/`load`.
     `include=None` → `sorted(discover())`; names are merged in selection order.
     An unknown name → `LookupError`. **One node type, one owner**: a name declared twice raises
     `DuplicateNodeTypeError` (a `ValueError` subclass, in `coral_app/errors.py`, re-exported here) — whether
     the second declaration comes from another plugin or collides with one of the host's
     `BUILTINS`. A name claimed by a function *and* a class escapes this check, because the two
     surfaces are merged into two separate maps; `nodeports.build_port_table` is where they meet and raises
     the same error. There is nothing to
     arbitrate: a graph names only the node type, so a silently displaced `list_append` would change what every
     graph on the platform computes while the JSON looks identical. `build_function_map` still applies
     `BUILTINS` **last**, which is now only about *key order* in `node_types.json`, not about precedence.
     This replaced the former "later wins" merge, which was never a designed rule but the behaviour of
     `dict.update()`; the single real duplicate it papered over — `print_result`, declared by both math and
     string — is gone, each plugin naming its own (`print_number` / `print_text`).
     `build_class_map` raises the same error for one class registered by two plugins under two
     keys, naming both, before the hierarchy check below could misread it.
     **Plugins do not share a class hierarchy**: `build_class_map` also raises a plain `ValueError`
     when a class registered by one plugin derives from a class registered by another, naming both
     classes and both plugins. The override rules are checked within one plugin's declarations, so
     across plugins nothing would check them.
   - Re-exports the two host-owned node surfaces: `PRIMITIVES_MAP` (from `coral_app/primitives.py`)
     and `BUILTINS` (from `coral_app/builtin_nodes.py`), a `Plugin` declaring the 15 collection
     functions with the same decorators, merged without entry-point discovery.

   The rest of the host is **one job per module**, in stages (issue #23). Nothing imports backwards:
   `nodeports` knows callables but not graphs; `graph` knows graphs but not callables; `registry` and
   `executor` are two independent consumers that **do not import each other**.

   - **`nodeports.py`** (stage 2): `build_port_table(function_map, class_map, primitives)` takes the
     declarations and returns node type -> `NodePorts(kind, inputs, outputs, attribute)` — `inputs`
     and `outputs` each a list of `Port(name, annotation, instance, written, passthrough)` in port
     order, `attribute` the name a method is declared under (`None` for every other kind), and
     `.returns` the outputs that are return values. An abstract class
     gets an entry of kind `abstract`, with no ports and no signature read: it is not a node a graph
     may use, but its key must meet the duplicate checks. It reads each callable's
     signature, then applies `annotations=` (fill only: typing an annotated slot, including an
     explicit `Any`, raises), `inputs=` (relabel; labels must stay distinct) and `outputs=` (name),
     in that order; a key naming no parameter, or a method's instance, raises. An input's name is its
     parameter's or its label; an output's is the one declared with `outputs=`, else `""`. A
     **written** input (`writes=`, or a non-`const` method's instance) is also an output, its
     **pass-through** (`passthrough` = the input's index), named and typed as the input: the
     outputs are the instance if written, then the return values, then the written parameters in
     parameter order. Typed as the input, a subclass's instance passed through a base's node
     comes out as the base; the subclass's own node keeps its type. `writes=` names parameters
     as `inputs=` does, never the instance. Every port is passed by position, so a callable with
     no readable signature, or with a keyword-only, `*args` or `**kwargs` parameter, raises
     `ValueError` — which refuses many C-extension classes (`datetime.date`), though not all
     (`decimal.Decimal` has a readable, positional signature).
     The **single place** that derives a node's
     arity from a callable, so the registry and the executor can no longer disagree about it. A
     method's port 0 is its instance: its first parameter, whatever its name, re-emitted as
     `Port("self", cls, instance=True)`, `written` unless the method is `const`; a method with no
     parameter at all raises. A missing
     annotation is normalised to `Any`.
     `methods_of(port_table, class_name)` lists a class's `Class.method` entries. Also the only place
     the three node surfaces meet, so it is where **one name declared as two kinds** — a primitive and
     a function, a function and a class — raises `DuplicateNodeTypeError`; a node type named `list` /
     `set` / `dict` is such a case, since those are primitives. It raises the same for one class
     registered under two keys, and for a dotted function name equal to a declared method's
     `Class.method` key: a function `math.sqrt` and a class `math` declaring `sqrt` are refused.
   - **`graph.py`** (stage 3): `Graph(nodes, edges, port_table)` and
     `Graph.from_file(path, port_table)`. **Constructing one validates it** — see
     [Graph validation](#graph-validation). Exposes `.order`, `.node(id)`, `.ports_of(id)`,
     `.inputs_of(id)` (incoming edges sorted by `target_input`, built once), `.qualified_ids`
     (node id -> qualified id, validated as check 3), `.literals` (node id -> a primitive's value,
     read as check 11), `.name_of(id)` and `.describe(id)` (see
     [Workflow JSON Structure](#workflow-json-structure)). Takes the port table as plain data, so it
     imports neither `inspect` nor any plugin machinery, and its tests need no plugin installed;
     the host modules it imports are `nodestatus`, for check 3's rules, and `primitives`, for
     check 11's.
   - **`registry.py`** (stage 5): `generate_registry()` renders the port table into the platform's
     file format, `python_type_to_string()`, `save_registry_to_file(filename, plugins=...)`. Every
     decision about the *format* lives here — argument dicts, index numbering, the `[-1]`
     convention, a pass-through as one `pass_through` argument; the arity and annotations come from
     the port table.
   - **`executor.py`** (stage 4): `WorkflowExecutor(workflow_file, plugins=..., touch_dir=...)` —
     see [Data flow](#data-flow). Validation happens during construction, so `execute()` only walks,
     calls and stores. No `json`, no `graphlib`, no edge list — and no `pathlib`/`os` either: the
     status markers are written by `nodestatus.py`.
   - **`nodestatus.py`**: the per-node status markers — `qualified_ids(nodes)` (a pure function
     naming the files, which also owns the rules for what can *be* one of those names — `Graph`
     calls it as check 3) and `NodeStatusDir` (the context manager writing them). One external
     consumer's file format, held in one module the way `registry.py` holds the registry's: it is
     handed a plain mapping and a path, and imports neither `graph` nor `executor`. See
     [Per-node execution status](#per-node-execution-status).

4. **`coral-app/cli.py`** — Coral-compatible CLI entry point (argparse):
   - Global `-p/--plugin` names the plugins to load (comma-separated; empty = all installed).
   - `register` subcommand → `save_registry_to_file()` (writes `node_types.json` into the cwd).
   - `run` subcommand → `WorkflowExecutor(...).execute()`, forwarding `--touch-dir` (default
     `"./"`, the cwd — see [Per-node execution status](#per-node-execution-status)).
   - `plugins` subcommand → prints `discover()`, one name per line; imports no plugin.
   - Empty `-p` resolves to `discover()` (all installed), passed explicitly; a non-empty one is
     checked against it (unknown or repeated names → `parser.error`) before any subcommand runs.
   - Exposed as the `coral` console script; wrapped by `coral-py` for the platform.

### Workflow JSON Structure

**Network Files** (e.g., `network-from-fe.json`):
Located at: `workflow.nodes` and `workflow.edges`

Nodes are **lean**: each carries its `type` and its `qualified_id` (plus `value` for primitives);
the executor infers the kind from `type`, so `node_type`/`method_name` are not part of the graph.
The `qualified_id` is required — see [Per-node execution status](#per-node-execution-status) — and is
omitted from the shapes below, which show only what decides a node's kind:
- Primitive: `{"type": "<type>", "value": <val>}`; a collection's `<val>` is a JSON string,
  `{"type": "set", "value": "[1, 2, 3]"}`
- Function: `{"type": "<func_name>"}`
- Constructor: `{"type": "<ClassName>"}`
- Method: `{"type": "<ClassName>.<method_name>"}`

A node may also carry an optional **`name`**: a caption, not an address. The editor shows it as
the node's headline and the reference backend logs it; ids address, names describe. It is not
unique and never validated — anything but a non-empty string counts as no name
(`Graph.name_of`), so a graph never fails over it. It appears in the per-node log lines and, via
`Graph.describe` (`'2'`, or `'2' ('with_five')`), in every error that names a declared node.

Edge format:
- `{"source": "<source_id>", "target": "<target_id>", "source_output": <idx>, "target_input": <idx>}`
- **CRITICAL**: `target_input` determines parameter ordering for function/method calls

**Registry Files** (e.g., `node_types.json`):
- Auto-generated schema describing all available node types, in the DealiiX platform format
- **Keyed by each node's `type`** (primitives by type name, functions by name, constructors and
  abstract classes by class name, methods by `Class.method`) — the editor looks entries up as
  `registry[type]`
- Each entry has:
  - `type`: the node type string (equals the entry's key)
  - `arguments`: Array with `connection_type` ("input"/"pass_through"/"output"), `type`, and `name` (empty `[]` for primitives)
    — an input argument's `name` is its parameter's or its `inputs=` label; an output argument's
    is what `outputs=` declared, else `""`; the editor shows it as the socket's label
    — a `pass_through` argument is a written input (a non-`const` method's instance, or a
    parameter in `writes=`): one argument, named as its input, whose index is in both `inputs` and
    `outputs`, the C++ backend's shape for a non-`const` reference. It has no output argument of
    its own
  - `inputs`: List of input indices
  - `outputs`: List of output indices (`[-1]` for constructors/primitives, `[]` for abstract
    classes), in port order, which need not be ascending: a non-`const` method's instance,
    argument 0, comes first (`[0, 2]`), and a written parameter after the return values
    (`[2, 0]`). The editor reads the list in order
  - `node_type`: "primitive", "function", "constructor", "method", or "abstract". An `abstract`
    entry, the C++ backend's shape for a type never constructed, has empty `arguments` /
    `inputs` / `outputs`; the editor hides it from its palette
  - `value` (primitives only): the initial value the editor copies into a dropped node: `"[]"` for
    `list` / `set`, `"{}"` for `dict`, `"false"` for `bool`, `""` for every other primitive
  - `bases` (constructor and abstract entries, optional): the keys of every registered ancestor,
    in MRO order (so under multiple inheritance a parent may follow a grandparent). An
    unregistered class in between is skipped (its ancestors are still found); a type-name
    ancestor (`float`) is never listed. Absent when empty.
  - `derived` (constructor and abstract entries, optional): the keys of every registered
    descendant, in class-map order. Absent when empty. Both lists depend on the `-p` selection.
- **A socket's `type`** is one of the nine names in `PRIMITIVES_MAP`, or — for a class the class map
  holds — that class's **key**, the same string its constructor or abstract entry is keyed by.
  Anything else is `"any"`: a class no selected plugin registers, and every parameterised generic
  (`List[int]`, `Optional[X]`), even around a registered class.
- **Subclasses depend on the front end.** It types a constructor's output as `base ?? type` and
  matches types by exact string. `base` is no longer written, so until the front end adopts the
  planned rule `{type} ∪ bases ∪ {base}`, a subclass instance is refused where its base is
  expected — a known regression, shared with the C++ backend. Validation and execution are
  unaffected: check 8 uses `issubclass` and the executor `isinstance`, so every registered
  ancestor is accepted there. `coral-math` ships the case to check the rule end to end:
  `plugins/coral-math/tests/graphs/network-multiple-inheritance.json` wires a
  `Square(Regular, Rectangle)` into sockets typed `Rectangle` and `Shape`, which only `bases`
  exposes.

### Data Flow

```
  plugins ──[1]──> maps ──[2]──> port table ──┬──[3]──> Graph ──[4]──> results
                                              │            ^
  graph JSON ─────────────────────────────────┼────────────┘
                                              │
                                              └──[5]──> node_types.json
```

| stage | job | input | output | module |
| --- | --- | --- | --- | --- |
| 1 | load plugins, add the host's builtins | plugin names | `function_map`, `class_map` | `coral_app/__init__.py` |
| 2 | describe each node type | the maps | port table | `coral_app/nodeports.py` |
| 3 | read, validate, order the graph | graph JSON + port table | `Graph` | `coral_app/graph.py`, `coral_app/nodestatus.py` (check 3), `coral_app/primitives.py` (check 11) |
| 4 | execute | `Graph` + the maps | `results`, plus the status markers if a touch dir was given | `coral_app/executor.py`, `coral_app/nodestatus.py` |
| 5 | write the registry | port table | `node_types.json` | `coral_app/registry.py` |

1. **Discover/Load**: the host lists installed plugins (no import) and loads only the requested names.
2. **Build maps**: each loaded plugin's `functions()`/`classes()` declarations are merged into
   `function_map` / `class_map` (selection order; a duplicate name raises `DuplicateNodeTypeError`),
   then `BUILTINS.functions()` is added to `function_map` last — so the host's own nodes are present under every selection, and a plugin
   claiming one of their names is refused rather than ignored. Primitives come
   from the host `PRIMITIVES_MAP`. With no plugin at all, stage 1 still yields a complete surface: the
   primitives plus the 15 builtins.
3. **Describe node types**: `build_port_table()` turns the maps into one entry per node type — and
   raises `DuplicateNodeTypeError` if one name is declared as two kinds, the duplicate stage 2 sees
   because it holds all three surfaces at once (and if one class is registered under two keys).
   Each entry lists the node type's input parameters and
   its outputs. Stages 4 and 5 both read it; neither introspects again.
4. **Read, validate and order the graph**: `Graph.from_file()` loads `workflow.nodes` /
   `workflow.edges`, runs every check in [Graph validation](#graph-validation), and orders the nodes
   with `graphlib.TopologicalSorter` (`{node: predecessors}`, each ready batch sorted so the order
   follows the graph rather than JSON key order). A bad graph raises `ValueError` **here** — while
   `WorkflowExecutor` is being constructed, before any node runs.
5. **Execute**: `execute()` walks `graph.order`, and for each node collects its input values from
   `results` (via `graph.inputs_of()`, already in parameter order), resolves the callable, binds the
   values to its parameters positionally, and calls it. Nothing is validated at this point.
6. **Store**: results stored in `executor.results`, keyed by node id, for downstream nodes.

### Node Execution Model

Each node's kind is read from the port table — `graph.ports_of(node_id).kind`, one of `primitive` /
`function` / `constructor` / `method`; the fifth, `abstract`, never reaches the executor, since
check 4 refuses a node of that kind. The kind is decided in `nodeports.build_port_table()` by where
the entry comes from — `PRIMITIVES_MAP`, `function_map`, `class_map` (the constructor, or
`abstract`) or a class's declared methods, already keyed `Class.method`; no type name is split.
One name declared as two of them raises `DuplicateNodeTypeError`. Only a function can meet a
method key, since class keys and primitives contain no `.`: a function `math.sqrt` and a class
`math` declaring `sqrt` are refused.

**Primitive nodes** are the one special case, and they return early with the value `Graph` already
read (`graph.literals`): `primitives.read_literal` reads the node's `value` the way its declared
`type` says. A scalar is cast via `PRIMITIVES_MAP[type]` (the JSON protocol may carry it as a
string); a value the cast refuses (`int("")`) raises `ValueError` naming the node. `bool` is the
exception: it accepts only `true` / `false`, natively or as a string, since `bool("false")` is
`True`. `any` passes through unconverted and `none` is `None`. A collection's `value` must be a
JSON string, parsed with `json.loads`: an array for `list` / `set`, an object for `dict`. A native
array or object, the wrong shape, malformed JSON or an unhashable set element raises `ValueError`
naming the node, chained to the parser's own error where there is one. A missing `value` raises
`ValueError` naming the node, for every type but `none`. All of this happens while the `Graph` is
built (check 11), so a bad literal fails before any node runs.

**Every other node** runs the same four steps, written once:

1. **Collect input values** — `graph.inputs_of(node_id)` hands over the incoming edges already sorted
   by `target_input`, i.e. in parameter order. Each is read from `results`. Whether that result is a
   *bundle* of outputs to index into is decided by the **port table**, never by the value:
   `len(graph.ports_of(edge.source).outputs) > 1`. A single-output node therefore passes its value on
   whole whatever `source_output` says, and a multi-output node always indexes. Deciding it from the
   value instead (`isinstance(value, tuple)`) was issue #31: a runtime type cannot tell "three
   outputs, bundled" from "one output that happens to be a tuple". `graph.py:_output_annotation` asks
   the same question the same way.
2. **Resolve the callable** — the only three-way distinction left, and it cannot be removed, because
   a method's callable depends on one of its own inputs, the instance's class, known only at run
   time:

   | kind | callable | arguments |
   | --- | --- | --- |
   | function | `function_map[type].target` | all the values |
   | constructor | `class_map[type].target` | all the values |
   | method | the function `Plugin.classes()` resolved for `type(values[0])` under `ports.attribute` | all the values, the instance first |

   A method is looked up by its **attribute**, not by its node type, which `name=` may have changed;
   and for the instance's own class, never on the instance: only declared code runs, and a
   subclass's override runs only if the subclass is registered — which the output-class check below
   guarantees for every instance that reaches a method.

3. **Call** — a plain positional call, `target(*arguments)`. The values already arrive in port order,
   which *is* parameter order, so nothing here looks at the callable's signature; `executor.py` does
   not import `inspect` at all. A method's function is plain, so the instance is simply its first
   argument, and the same call works for all three kinds.
4. **Store** the result under the node id. A node with pass-throughs stores its outputs in port
   order: each pass-through is the very object its input received, modified; the return values are
   what the call returned. It is a tuple only when the node has more than one output, so a
   non-`const` method returning `None` stores its instance itself.

Four run-time checks survive in the executor, all there for the same reason: they are about
a *value*, not about wiring, so validation cannot have settled them in advance. Everything else was
verified before execution began.

| check | when | what |
| --- | --- | --- |
| **instance** | resolving a method's callable | input port 0 must really hold an instance of the class it is annotated with (`isinstance(instance, ports.inputs[0].annotation)`), the annotation check 8 validated the edge against |
| **output arity** | right after a node returns | a node declaring n > 1 return values must have returned a tuple of exactly n; pass-throughs are not counted |
| **shared output** | right after the arity check | an output feeding a writer holds an object (by identity) no other output of the node holds: `return self`, or one object returned twice, would otherwise be modified with nothing ordering it against the other output's consumers |
| **output class** | right after the shared-output check | every output value that is an instance of a registered class must be of a registered class itself (`type(value)` in the class map), whatever the port's annotation, `Any` included |

The **output arity** check exists because the port table's arity comes from a return annotation,
which is a *claim* by the function's author. Everything downstream trusts it: the registry emits that
many sockets, checks 7 and 8 bound and type an edge by it, and step 1 above indexes with it. This is
the one place the claim meets what the function actually returned, and it is placed at the *producing*
node rather than at a consumer's edge so that it fires whether or not the offending port is wired —
an under-declared node cannot slip through by nobody reading its last output. The error names the
function whose annotation is wrong, not the graph that believed it:

```
Node '3' of type 'phiflow_iterate' declares 3 return values but returned a tuple of 2
Node '3' of type 'phiflow_iterate' declares 3 return values but returned int
```

A named node adds its name after the id: `Node '3' ('step') of type 'phiflow_iterate' …`.

Only n > 1 is checkable. At n == 1 a returned tuple is legitimate — that is the `-> tuple` case — so
there is nothing to compare; at n == 0 nothing returned is ever read, since the node's outputs, if
any, are its pass-throughs. Nothing here checks the *types* of a tuple's elements; check
6 reasons about the declaration only.

The **output class** check exists because a method node runs the function declared for its
instance's class. A function annotated with a registered base may return an instance of a subclass
no plugin registers, whose methods nobody declared and no override rule checked. Like the arity
check it confronts a declaration with a value, so it cannot run earlier, and it fires at the
producer, before any consumer of the value has run:

```
Node '0' of type 'make' produced on output 0 an instance of Hidden, a subclass of 'Base' that no selected plugin registers; register it, so that the methods it runs are declared
```

### Per-node execution status

While a graph runs, the executor drops one **empty file per node per state** into a directory the
platform watches — this is how the editor lights each node up live (issue #30). The convention is
the C++ reference backend's, because the platform's consumer was written against that producer:

| moment | file | note |
| --- | --- | --- |
| before a node runs | `<qualified_id>.running` | empty |
| the node returned | `<qualified_id>.succeeded` | empty |
| the node raised | `<qualified_id>.failed` | empty; `.running` is **left in place**, as in C++ |

The consumer lists the directory with `ls -tr` and splits each name on `.`, so **file mtime order is
the timeline** and a `.` inside a qualified id mis-keys it. Nothing is ever written twice in a run —
the three suffixes differ and the directory is cleaned at startup — so the mtimes are exactly the
call order. (Caveat inherited from the kernel's coarse file-timestamp clock, ~1 ms: nodes that run
faster than that share an mtime and cannot be ordered. C++ writes through the same clock.)

**All nodes get markers, primitives included** — C++ makes every node a task with no exemption, and a
graph whose primitives never appear would read as "half the nodes never started".

**The filename comes from the node's `qualified_id`**, a field the platform uses for a node's path
through nested subgraphs, and **every node must declare one**: a node without it, or two nodes
sharing one, raise `ValueError` while the `Graph` is being constructed (check 3: the rules live in
`nodestatus.py`, which owns the filename convention, and `Graph` is what applies them). This is the
one place the C++ backend is not followed — it invents
`<node_id>_auto_<counter>` and warns. An invented name is not the node's identity, so a graph that
omits the field would hand the platform a timeline it cannot key back to its nodes; and note that
node ids and qualified ids are not the same thing (a node id is unique only within one graph), so
nothing derives one from the other. Every graph the repo ships therefore carries a `qualified_id`
per node, numbered progressively in declaration order.

**The mapping is built by `Graph`, whether or not markers are written**: a graph must not become
valid or invalid depending on an unrelated flag, and "every node declares a unique, filename-safe
`qualified_id`" is a rule about node *identity*, which belongs with the other checks rather than in
the executor. `WorkflowExecutor` reads `graph.qualified_ids` and computes nothing of its own.

Because the value becomes a filename, `qualified_ids()` also rejects one that cannot be one — a
**non-string** (`12` and `"12"` are distinct values naming one file, and C++'s `get<std::string>()`
throws on a number), the **empty string** (it would write `.running`), a **`.`** (the consumer
splits on it) and a **path separator** (it would leave the watched directory). Each is a way for two
nodes to write the same markers, or for the consumer to key one to the wrong node.

Consequence for the platform: a graph its editor exports without `qualified_id` runs under the C++
backend and is rejected here.

**Where they go**: `--touch-dir`, and its default is `"./"` — the cwd. C++ has no "write nothing"
mode (it defaults the same way and touches unconditionally), and the CLI is the platform's contract,
so fidelity holds there: `coral run graph.json` in a checkout *will* drop markers in that directory
and clean the matching files already in it. The library object is the other way round:
`WorkflowExecutor(..., touch_dir=None)` writes nothing, which is what keeps the test suite from
having to hand every executor a `tmp_path`. The directory is prepared on the **first line** of
`__init__`, before plugin loading and before validation, so a bad path fails before phiflow is
imported and a graph that fails validation shows the platform an *empty* directory rather than the
stale timeline of an earlier job.

**Two asymmetries, both deliberate** (and both C++'s):

| failure | behaviour | why |
| --- | --- | --- |
| the directory cannot be created or cleaned | raises, at t=0 | a bad `--touch-dir` is a configuration error, and failing costs nothing yet |
| a marker cannot be written mid-run | warns **once**, keeps executing | once nodes are running, the graph's result is worth more than its telemetry |

**The exception a failing node raises is propagated untouched** — type and message both. C++ re-throws
a `runtime_error` wrapping the node id; we do not, because the `try/except` only exists when a touch
directory was configured, so wrapping would make a diagnostic's *shape* depend on `--touch-dir`. The
node id reaches the log the other way, unconditionally: `execute()` prints
`Start running node N [qid]: name (type = T)` before each node and
`Node N [qid]: name (type = T) run` after it, mirroring C++'s `slog_info` pair, so a traceback is
always bracketed by lines naming the node. An unnamed node drops `: name` — where C++ prints an
empty one — rather than inventing a name nobody wrote.

### Graph validation

**The graph is fully validated before execution starts.** Constructing a `Graph` runs every check
below; a graph that constructs is a graph that can be executed. Because `WorkflowExecutor.__init__`
builds one, a defect surfaces there — never after a long PhiFlow run has already started. Each
failure raises `ValueError` naming the offending node or edge (edges by their key in the graph JSON,
nodes by their id followed by their `name` when they have one).

In order — one item per check, as `Graph.__init__` runs them:

1. every edge `source` and `target` names a declared node — **first**, because
   `TopologicalSorter` would otherwise silently materialise an unknown predecessor as a node;
2. no node carries a **nested workflow** (a subnetwork: `"node_type": "network"`, or a `workflow`
   inside its `value`). It runs before the type check so such a node is rejected by name rather
   than as "unknown type `coral::Network`". That shape is the one in which node ids stop being
   unique: the inner `nodes` object numbers from its own zero, and only the `qualified_id` (`12_3`
   — node 3 of the subnetwork at node 12) separates the two;
3. every node declares a `qualified_id` that is unique and can be a filename — the only check whose
   rules live in another module: `nodestatus.qualified_ids()` owns them, because it owns the
   filename convention they come from; `Graph` applies them and keeps the resulting mapping on
   `.qualified_ids`. See [Per-node execution status](#per-node-execution-status);
4. every node `type` has a port-table entry, and not an `abstract` one: a class that only types
   sockets has nothing to run (the C++ backend lets such a node through and yields a null pointer);
5. per target node, the `target_input` values are exactly `{0 … n-1}` for n incoming edges — catches
   two edges on one port and a port index out of range;
6. the incoming edge count equals the type's input count — catches missing and extra connections;
7. every `source_output` names an output the source type has;
8. every edge's source annotation is compatible with its target annotation;
9. **one writer per value**: an output feeds at most one written input (`source_output` normalised,
   so `0`, `-1` and an omitted key are one output of a single-output node), and the writer does not
   also receive it on a read input — it would read the value while modifying it, inside one call;
10. no cycles — the message names the cycle path. Besides the edges, every node reading an output
    that check 9 found a writer for is ordered before that writer, as if an edge joined them; a
    cycle closed by such an implicit edge is named too: which node reads which value, which node
    modifies it;
11. every primitive's `value` is present (unless its type is `none`) and can be read as its type
    says (`primitives.read_literal`). The parsed values are kept on `.literals`, so the executor
    never parses one — see [Node Execution Model](#node-execution-model).

**Every argument must be connected** (check 6). A default value in plugin code is *not* a way to
leave a port unwired, so the defaults in `phiflow_union`, `phiflow_iterate`,
`phiflow_plot_and_save`, `Calculator` and `StringProcessor` are unreachable from a graph. This is
long-standing behaviour, moved earlier.

**Readers before the writer (checks 9 and 10).** A value fanned out to several nodes, one of which
modifies it in place, would otherwise give a result decided by node ids: the order breaks ties by
id. So every reader of a written value runs before its writer and sees it unmodified, and a reader
that should see the modified value reads the writer's pass-through output instead, which is an
ordinary edge. Two writers of one value are refused, since nothing would order them: chain them,
the second fed from the first's pass-through. No copy protects a reader, by the host or by a node:
the order does. (The executor does copy each literal per run, so that a writer cannot change the
graph's literals.)

**`source_output` (check 7)** — both `0` and `-1` appear on the wire for a single-output node, so
both are accepted there:

| output count | accepted `source_output` |
| --- | --- |
| 1 | `0`, `-1`, or the key omitted |
| n > 1 | `0 … n-1` |
| 0 (returns `None`) | none — the node has nothing to pass on, so any outgoing edge is an error |

The three spellings for a single output are synonyms **in fact**, not only on paper: the executor
takes the output count from the port table, so it never reads `source_output` on a single-output node
and all three deliver the same value (issue #31 — they used to deliver three different ones). On such
a node `source_output` is genuinely ignorable. This is also why the executor does not re-check the
index: check 7 already bounds it, and duplicating that would put the same rule in two places.

**Edge type compatibility (check 8)** is deliberately narrow: it skips whenever the answer is not
certain, because wrongly refusing a good graph is worse than not checking one.

| source | target | verdict |
| --- | --- | --- |
| `Any`, or no annotation | anything | skip |
| anything | `Any`, or no annotation | skip |
| a class | the same class, or a base of it | accept |
| a number | a method's instance (port 0) of a numeric class, e.g. `Fraction` | **reject** unless the same class or a subclass — the executor checks the instance with `isinstance`, so no widening reaches it |
| `bool` | `int` | accept — `bool` really is an `int` subclass |
| `int` | `float` | accept — numeric widening |
| anything | `bool` | **reject** — widening never lands on `bool`; only `bool` itself is accepted |
| a class | an unrelated class, or a scalar | **reject** |
| `str` -> `float`, `float` -> `int`, `none` -> `float`, … | | **reject** |
| a union, a generic alias | | skip — `issubclass` cannot judge it |

`graph.py` names no coral type to do this. Everything decidable comes from `issubclass` over the
annotations the plugins declare; the single relation the class hierarchy cannot express — `int` is
accepted where a `float` is expected, though `issubclass(int, float)` is `False` — is taken from the
standard library's own `numbers` tower rather than a hand-written table.

The check only sees what a node's author declares, so **annotation quality is the author's
responsibility**. A *slot* below is one annotation the check can look at — every input and output of
every node type, except a method's `self`, as input or as its pass-through output (which the port
table synthesises from the class). Across
the four plugins and the host's builtins, 167 of 199 slots are checkable and 32 are `Any` — and every
one of the 32 is in phiflow or in the builtins, where 9 are deliberate (see below):

| source | slots | `Any` | checkable |
| --- | --- | --- | --- |
| math | 50 | 0 | 50 |
| string | 8 | 0 | 8 |
| phiflow | 48 | 23 | 25 |
| pypde | 57 | 0 | 57 |
| builtins (host) | 36 | 9 | 27 |

So `phiflow_iterate` returning `Tuple[Any, Any, Any]` cannot be checked, and a grid wired where a
float belongs only fails once the simulation has run. A plugin that annotates properly gets its
wiring verified at t=0; one that writes `Any` does not. Fixing that is a plugin change, and belongs
to whoever owns the plugin. This is the same bargain the registry already strikes (see
[Type Hint Requirements](#type-hint-requirements)).

The builtins' 9 `Any` slots are **deliberate and not fixable**: they are exactly the element and key
positions (`list_append`'s `item`, `dict_set`'s `key`/`value`, `list_get`'s return, …). A collection
holds anything, so there is nothing truer to write there — and writing `List[int]` instead would make
the check skip the *container* edge too, trading 27 checkable slots for 0. The 22 collection slots
that are checkable are precisely what decision 3's type names bought.

### PhiFlow Integration

PhiFlow physics simulations (fluid dynamics — smoke plumes, obstacles) are exposed to the workflow
system by the `phiflow` plugin. Wrapper classes in
`plugins/coral-phiflow/src/coral_plugin_phiflow/__init__.py` provide a simplified,
type-hinted API for workflow integration; the plugin owns the `phiflow`/`jax`/`h5py` dependencies.

### Built-in collection nodes

Lists, sets and dictionaries are operated on by **host** functions in `coral_app/builtin_nodes.py`, not
by a plugin (issue #25). They are available under **any** `-p` selection and with no plugin installed at
all, exactly like the primitives — a graph using them runs anywhere a coral host runs.

| | create | add | extract | inspect | remove |
| --- | --- | --- | --- | --- | --- |
| **list** | `list_new` | `list_append` | `list_get` | `list_size` | `list_remove_at` |
| **set** | `set_new` | `set_add` | `set_to_list` | `set_size` | `set_remove` |
| **dict** | `dict_new` | `dict_set` | `dict_get` | `dict_size` | `dict_delete` |

A collection can also be written as a **literal**: a primitive node whose `value` is a JSON string,
`{"type": "list", "value": "[10, 20, 30]"}` (see [Node Execution Model](#node-execution-model)). This
is the reference C++ backend's model, which registers `std::set<unsigned int>` as an elementary type
carrying `"[1, 2, 3]"`. The type strings still differ (`set` vs `std::set<unsigned int>`), as the
scalars already do (`float` vs `double`), so a graph using one runs on one backend only. The two
forms are complementary: a literal cannot hold computed values, the operations can. `list_new` /
`set_new` / `dict_new` duplicate the empty literals and stay.

A literal is JSON, with JSON's limits: a `dict` literal's keys are always strings, so `dict_get` on
it with an `int` key raises `KeyError`; a `set` literal collapses elements Python holds equal
(`"[1, 1.0, true]"` is `{1}`); and a nested array inside a `set` literal is unhashable and raises
`ValueError` naming the node.

Three properties hold for all 15, and graphs depend on each:

- **Pure.** Every operation returns a *new* collection and never mutates its input. A node's result is
  read by every downstream consumer in an order the topological sort chooses, so in-place mutation would
  make the graph's outcome depend on that choice. The copy is shallow: a collection holds references,
  so a mutable element modified by a writer elsewhere is seen modified through every collection
  holding it.
- **Fail loud.** A missing index or key raises (`IndexError` / `KeyError`); `set_remove` uses `remove`,
  not `discard`. No `None` fallbacks and no default arguments — graph check 6 requires every port to be
  wired, so a default would be unreachable.
- **No element typing.** Annotations are the bare `list` / `set` / `dict`, elements are `Any`. A generic
  alias would make graph check 8 skip the container edge as well (see the note under
  [Graph validation](#graph-validation)).

Two details worth knowing before touching them:

- `set_to_list` returns `sorted(s)`, not the iteration order. A set of strings iterates differently
  **between runs** (hash randomisation), which would make a graph non-reproducible; the price is
  `TypeError` on mutually incomparable elements, which is accepted because such a set has no defined
  order for a graph to depend on anyway.
- Names are underscored. In a node type a dot already means a module (`math.sqrt`) or a class
  (`Calculator.add_to_value`), and `list.append` is real Python for a method with *different* semantics
  (mutates, returns `None`) — the name would assert something false.
- `list_new`/`set_new`/`dict_new` are the first **function** nodes with zero inputs (`inputs: []`,
  `outputs: [0]`); primitives also take no input but use `outputs: [-1]`. This is the platform-facing
  novelty to confirm in the editor.

Runnable examples: `coral run coral-app/examples/collections/list.json` (also `set.json`,
`dict.json`, and `literals.json` for the literal form) — they ship with the host, because the host
is what provides their node types. The
"needs no plugin" property is asserted by `coral-app/tests/test_examples.py`, which passes
`plugins=[]` — the CLI cannot express it, since an empty `-p` means *all* installed plugins.

## Key Constraints and Design Decisions

- **Edge ordering is critical**: Function/method parameter order determined by `target_input` values on edges (sorted ascending)
- **Type system**: maps Python types to the protocol's type-name strings. The table is
  `PRIMITIVES_MAP` in `coral_app/primitives.py`, and every name in it is a *primitive node* type, a
  node carrying a literal in its `value` field: `int`, `float`, `str`, `bool`, `any`, `none`, cast by
  the declared type (`any` passed through, `none` is `None`), and the collections `list` / `set` /
  `dict`, whose `value` is a JSON string. `registry.py` renders socket types from the same table, so
  every socket type name is also a `registry[...]` key. So no node type may be named after a
  primitive: `build_port_table` refuses one with `DuplicateNodeTypeError`. The second source of
  socket type names is the **registered classes**, written as their class-map key (see *Registry
  Files*); a class registered under two keys is refused the same way, since it would have two names
- **Node ids are decimal integers**, and the loader enforces it: node keys, edge keys and both
  endpoints of every edge go through `graph.py:_read_id`, which raises `ValueError` while the `Graph`
  is being constructed. The protocol keys nodes by integer and three platform mechanisms rest on it:
  the reference C++ backend reads each key with `std::stoi` into an `unsigned int`, the platform's
  exporter `parseInt`s every edge endpoint — a word id becomes `NaN`, which `JSON.stringify` writes
  as `null`, so the graph comes back with its wiring gone — and the editor's id counter `parseInt`s
  every node id to find the next free one. Leading zeros and negative ids are rejected too
  (`std::stoi("01")` is `1`, so `"01"` and `"1"` would name one node), as are the non-ASCII digits
  `str.isdigit` accepts and `std::stoi` does not. Ids are still *keyed* as strings — **both** node
  keys and edge endpoints are coerced with `str()`, because the editor writes endpoints as numbers
  while JSON object keys are always strings, and coercing one side only was incoherent — and because
  that coercion can *merge* two keys (`0` and `"0"`), two ids denoting the same node raise instead of
  the later declaration silently overwriting the earlier. A graph from a file cannot reach that: JSON
  object keys are strings. Note what is *not* required: a `qualified_id` need only be unique and
  filename-safe (check 3), not equal to its node id — the reference backend requires no more, and a
  flattened subgraph would legitimately carry `12_3`. Consequence for test data: node ids carry no
  meaning, so where a node's role matters it belongs in the node's optional `name` (see
  [Workflow JSON Structure](#workflow-json-structure)), which the JSON carries and the editor
  shows, and a test looks the node up by it (`node_named` in the plugin's `<n>_suite.py`)
- **No cycles**: Workflow graphs must be acyclic (DAG) — `graph.py` raises `ValueError` naming the
  cycle path, using `graphlib.TopologicalSorter` (stdlib, `{node: predecessors}`)
- **Readers before the writer**: a value one node modifies in place has one writer, and every
  other node reading it runs first (checks 9 and 10). What a node modifies is declared, with
  `const=` and `writes=` — see Core components
- **Plugins do not share a class hierarchy**: a class registered by one plugin may not derive from
  one registered by another (`build_class_map` raises). With the output-class check, a method node
  runs only code its own plugin declared
- **Validate before executing**: every defect — identity, wiring, typing, ordering, literals — raises while the `Graph` is being constructed, so
  `WorkflowExecutor(...)` fails before the first node runs — see [Graph validation](#graph-validation)
- **One job per module**: `nodeports` knows callables but not graphs; `graph` knows graphs but not
  callables (it never imports `inspect` or a plugin; its host imports are `nodestatus`, for
  check 3's filename rules, and `primitives`, for check 11's literals); `executor` receives an
  already-validated graph
  (no `json`, no `graphlib`, no edge list). `tests/invariants/test_source_rules.py` enforces these
  boundaries by reading the source
- **Lazy discovery**: `discover()` never imports a plugin; `load(name)` imports only that one. An unselected
  `phiflow` is never imported, so its heavy deps aren't paid for.
- **Fail-loud on unknown plugin**: an unknown / not-discoverable `-p` name, or a repeated one, is
  refused by the CLI (exit status 2) before anything runs; `load()` raises `LookupError` for an
  unknown name; an installed-but-broken plugin raises `ImportError` at load. No silent partial state.
- **No `from __future__ import annotations`** (project-wide): it stringizes annotations, which would make
  `registry.py:python_type_to_string` see `"float"` instead of `float` and collapse every socket to `"any"`. A
  guard test (`tests/invariants/test_source_rules.py`) enforces this across every package's `src`.
- **No issue, PR, plan-step or decision numbers in code**: docstrings and comments in every
  package's `src` and in the test suites document the code as it stands, never how it got there.
  Never write `issue #31`, `PR #12`, `Step 3.4`, `decision 2`, or `see the plan` — `git blame` and
  the commit message carry that link, and they stay correct when an issue is closed or renumbered.
  Keep the reasoning, drop the citation: reword the sentence so it stands on its own. `issues/` is
  the historical record and is exempt.
- **Naming conventions**:
  - Functions: the node type is `__name__`, or `name=`, which may contain `.` (e.g., `"add"`,
    `"math.sqrt"`)
  - Classes: the class key is `__name__`, or `name=`, without `.`; it is the constructor's `type`
    (e.g., `"Calculator"`)
  - Methods: the node type is derived as `<class key>.<name>`, `name` being `__name__` or `name=`
    without `.` (e.g., `"Calculator.add_to_value"`); it is never written whole
  - Plugin entry-point names (`math` / `string` / `phiflow` / `pypde`) are the platform-facing identity — do not change them.
- **Type hint requirement**: every parameter and return must be typed, in the code or with
  `annotations=`, for proper registry generation
- **C extension limitation**: a C-extension class registers its constructor only if a signature
  can be read from it and every parameter is positional (`decimal.Decimal` can; `datetime.date`
  cannot). None of its methods can be declared: they are not plain functions. Wrap it in a
  pure-Python class

## Adding a New Plugin

To add support for a new library or capability, create a **new plugin distribution** under `plugins/`. Nothing
in `coral-core` or `coral-app` changes — the host discovers the plugin at runtime once it's installed.

1. **Create the package skeleton** `plugins/coral-<name>/`:
   ```
   plugins/coral-<name>/
   ├── pyproject.toml
   └── src/coral_plugin_<name>/__init__.py
   ```

2. **Create the plugin and declare its node types on it** (type hints are required — the registry
   is annotation-driven). A callable defined elsewhere needs no wrapper when `annotations=` can
   supply the types its signature lacks; a wrapper is still the way to adapt an API:
   ```python
   # src/coral_plugin_<name>/__init__.py
   import math
   from typing import Tuple
   from coral_core import Plugin

   plugin = Plugin()

   @plugin.function
   def my_function(param1: float, param2: str) -> int:
       """Function description"""
       ...

   @plugin.function(outputs=("quotient", "remainder"))   # optional: labels the outputs in the editor
   def my_divmod(a: int, b: int) -> Tuple[int, int]:
       ...

   @plugin.cls
   class MyClass:
       def __init__(self, x: float = 0.0): ...

       @plugin.method                  # only declared methods become nodes; this one modifies self
       def do_thing(self, amount: float) -> float: ...

       @plugin.method(const=True)      # a method that leaves self unchanged must say so
       def peek(self) -> float: ...

   @plugin.function(writes="buffer")   # modifies a parameter in place: a pass-through output
   def fill(buffer: list, value: float) -> None: ...

   # A callable defined elsewhere, declared as it is
   plugin.function(math.fmod, name="math.fmod",
                   annotations={"x": float, "y": float, "return": float})
   ```

3. **Declare the entry point and dependencies** in `plugins/coral-<name>/pyproject.toml`:
   ```toml
   [build-system]
   requires = ["hatchling"]
   build-backend = "hatchling.build"

   [project]
   name = "coral-plugin-<name>"
   version = "0.0.0"
   requires-python = ">=3.12"
   dependencies = ["coral-core"]   # + any real libraries this plugin wraps (e.g. "numpy")

   [project.entry-points."coral.plugins"]
   <name> = "coral_plugin_<name>:plugin"

   [tool.hatch.build.targets.wheel]
   packages = ["src/coral_plugin_<name>"]
   ```
   Because the plugin **declares** its heavy dependencies here, installing it guarantees they're importable — a
   broken/partial install fails loud with `ImportError` (there is no `try/except AVAILABLE` guard).

4. **Add the package to the workspace sources** in the root `pyproject.toml`:
   ```toml
   [tool.uv.sources]
   coral-plugin-<name> = { workspace = true }
   ```
   (`[tool.uv.workspace] members = [..., "plugins/*"]` already includes the directory.)

5. **Sync and regenerate the registry**:
   ```bash
   uv sync
   coral -p "<name>" register --output=/tmp/check.json
   coral -p "<name>" run my_test_graph.json
   ```
   The plugin's entry point is discovered automatically; `discover()` will list `<name>`.

6. **Give it a test suite.** Copy the shape every plugin here uses — this is the step the recipe used
   to be missing, and the reason a third-party plugin author had nowhere to put a test:

   ```
   plugins/coral-<name>/
   ├── examples/                       # optional: graphs a user is told to run
   └── tests/
       ├── <name>_suite.py             # PLUGIN_NAME, MODULE_NAME, INSTALLED, paths to graphs/golden
       ├── conftest.py                 # fixtures + the collect-time guard (see below)
       ├── graphs/                     # editor exports this plugin owns
       ├── unit/                       # its functions and classes, plus its Plugin conformance.
       │   │                           #   Imports only itself and `coral_core`.
       │   └── test_plugin_present.py  #   the entry-point name, and that it is *this* package's
       └── system/                     # its graphs through the host; `coral_app` allowed here
           ├── test_graphs_validate.py #   every shipped graph constructs a Graph — never executes
           ├── test_graphs_run.py      #   they execute, with real value assertions
           ├── test_registry.py        #   its slice of node_types.json, byte-compared
           └── golden/node_types.<name>.json
   ```

   Three conventions, each with a reason:

   - **`PLUGIN_NAME` is hardcoded** in `<name>_suite.py`. That is not the forbidden "plugin catalog":
     it is a self-reference inside the package that declares the name in its own `pyproject.toml`, and
     deriving it from installed metadata would silently follow a rename — destroying the one assertion
     worth having, since the name is what the platform's `-p` selects.
   - **The suite guards itself.** `conftest.py` reads its own entry point and, when absent, sets
     `collect_ignore_glob = ["system/*"]` plus a scanned `collect_ignore` for every `unit/` module but
     `test_plugin_present.py`, because importing the others imports the plugin. That one imports
     nothing from it, so it survives to report a visible skip.
   - **`coral-app` is a test-only dependency**, declared as a PEP 735 group so it never reaches the
     wheel:

     ```toml
     [dependency-groups]
     test = ["coral-app"]
     ```

     Then `uv sync --group test`. Outside this workspace, that group is what makes `tests/system/`
     installable at all.

**How registration works internally:**
1. Constructor nodes are generated from the class's signature (`inspect.signature(cls)`), except
   for an abstract class, which has none and whose signature is never read.
2. Method nodes are generated only for declared methods, inherited ones included (see Core components).
3. Methods use fully qualified names: `ClassKey.name`, `name` defaulting to the method's `__name__`.
4. First input to method nodes is always the instance; unless the method is `const`, it is also the
   first output, a pass-through.

**Limitations:**
- Every port is passed by position, so a parameter that is keyword-only, `*args` or `**kwargs` is
  refused, and the whole node type with it.
- A C-extension class registers its constructor only if a signature can be read from it and every
  parameter is positional (`decimal.Decimal` can; `datetime.date` cannot). None of its methods can
  be declared: they are not plain functions. Create a pure-Python wrapper class.

### Type Hint Requirements

The registry system requires explicit type hints:
- Use basic Python types: `int`, `float`, `str`, `bool`
- Use `Any` from `typing` for flexible types (note: has issues with `function-schema` library)
- Return type `None` indicates no output
- Missing type hints default to `"any"` in registry; `annotations=` supplies them for a callable
  whose source cannot be annotated (a builtin, another library's class). It only fills: a key for an
  already annotated slot raises. A value must be the type itself, not its name: a `str` raises,
  since it is never resolved; for a class defined later, use the call form once the class exists
- A class annotation renders as the class's key only if a selected plugin registers that class;
  otherwise it is `"any"`. Generics (`List[X]`, `Optional[X]`) are always `"any"`
- A **tuple return must declare its elements**: `Tuple[float, str]` is two output ports. Bare `Tuple`,
  `Tuple[()]` and `Tuple[Any, ...]` are rejected by `build_port_table` with a `ValueError` naming the
  function — the first two would yield *zero* ports, and the variadic form has no static arity and
  would yield a port annotated `Ellipsis`. Plain lowercase `tuple` is legal and different: **one**
  output port whose value happens to be a tuple, passed on whole. The rejection fires while the port
  table is built, i.e. at `coral register` and at every `WorkflowExecutor` construction, so one badly
  annotated function fails the host rather than yielding a wrong registry
- A function must return what its annotation declares: a node declaring n > 1 outputs returning
  anything but a tuple of exactly n raises at run time (see [Node Execution Model](#node-execution-model))
- **Naming outputs**: a return value has no name, so every output is written with `"name": ""`
  unless its declaration gives `outputs=`, one name per return value, in order —
  `@plugin.function(outputs=("velocity", "smoke", "pressure"))` on a `-> Tuple[Any, Any, Any]`. It
  works on functions and methods; a subclass inheriting a declared method inherits its names. A
  pass-through output is not named there: it is named as its input. A
  name count different from the return-value count (including any name on a `-> None`) is rejected
  by `build_port_table` with a `ValueError` naming the node type. `plugin.cls` takes no `outputs=`:
  a constructor's output is the instance, written as `outputs: [-1]` with no argument to carry a
  name. Names are labels only — wiring stays positional (`source_output`)
- Do **not** use `from __future__ import annotations` (see Key Constraints above)
