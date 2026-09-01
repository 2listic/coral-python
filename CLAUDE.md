# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Coral for Python** is a workflow execution system that processes computational graphs defined in JSON format. The system supports four types of nodes:
- **Primitive nodes**: Hold constant values (int, float, string, bool, any)
- **Function nodes**: Execute Python functions with typed inputs and outputs
- **Constructor nodes**: Instantiate Python classes
- **Method nodes**: Call instance methods on objects created by constructor nodes

The four kinds are unchanged by where a node comes from, but note that not every node comes from a
plugin: besides the primitives, the host ships **function** nodes of its own — the collection
operations in `coral_app/builtin_nodes.py`, available with no plugin installed at all. See
[Built-in collection nodes](#built-in-collection-nodes).

The project uses PhiFlow for physics simulations and numerical computing.

The repo is a **uv workspace / monorepo**: a small set of independently installable distributions
under `packages/*`. A minimal contract package (`coral-core`) defines a `Plugin` ABC; the host
(`coral-app`) discovers and loads plugins at runtime via `importlib.metadata` entry points; each
capability (`math`, `string`, `phiflow`) is its own `coral-plugin-*` distribution. See
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
excluded). Install it once per clone with `uv run pre-commit install`. Tests are deliberately not in
the hook (no runners yet).

```bash
uv run pre-commit run --all-files   # everything the hook would do, over the whole repo
uv run ruff format packages tests
uv run ruff check packages tests
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
subcommands. `-p/--plugin` must precede the subcommand.
```bash
# Run a workflow graph (graph path required; all installed plugins by default)
coral run path/to/workflow.json
coral -p "math" run path/to/workflow.json
coral -p "math,string,phiflow" run examples/phiflow/network-from-fe.json

# Send the per-node status markers somewhere other than the cwd
coral run path/to/workflow.json --touch-dir /run/job-42

# Generate the node registry (writes node_types.json into the cwd)
coral register
coral -p "math" register
coral register --output="custom-registry.json"
```

The `coral-py` launcher wraps this for the DealiiX platform: it runs the `coral` console script inside the uv
workspace (`exec uv run --quiet --project "$HERE" coral "$@"`) while preserving the caller's cwd (so `register`
writes `node_types.json` there). Point the platform's `coralBinaryPath` at `coral-py` and set `coralPluginPath`
to the plugin list.

**Default plugin behavior**: When `-p/--plugin` is omitted, all installed plugins are loaded (via entry-point
discovery, in `sorted(discover())` order). Primitives are always included. An unknown / not-discoverable `-p`
name fails loud with `LookupError` (no silent partial registry).

**Available plugins** (each an installed `coral-plugin-*` distribution, registered under the `coral.plugins`
entry-point group):
- `math` - Mathematical operations and Calculator class
- `string` - StringProcessor class
- `phiflow` - PhiFlow physics simulation wrappers

### Running Tests
```bash
# Run all tests (from the workspace root, against the editable-installed packages)
pytest

# Run with coverage
pytest --cov=. --cov-report=html
open htmlcov/index.html

# Run specific test file
pytest tests/test_executor.py
pytest tests/test_integration.py

# Run specific test class or function
pytest tests/test_executor.py::TestPrimitiveNodeExecution
pytest tests/test_executor.py::TestPrimitiveNodeExecution::test_int_primitive

# Run tests by category (using markers)
pytest -m integration  # Integration tests with JSON network files
pytest -m math         # Math plugin tests
pytest -m phiflow      # PhiFlow tests
pytest -m string       # String plugin tests
```

**Plugin-set-agnostic suite**: the suite passes under any install subset/superset, not only the
fully-synced workspace. Discovery/load *mechanics* tests derive names from `discover()` (never a
hardcoded catalog); any test needing a specific plugin's nodes is tagged `@pytest.mark.<plugin>`
(`math`/`string`/`phiflow`, class-level `pytestmark` when the whole class needs it).
`tests/conftest.py::pytest_collection_modifyitems` **auto-skips** a plugin-tagged test when that
plugin isn't in `discover()` (keyed on the `packages/coral-plugin-*` the repo ships, so it tracks the
set automatically) — a missing plugin yields clean skips, not `LookupError`. Verify a subset with
`uv pip uninstall coral-plugin-<x>` then `uv run --no-sync pytest` (the `--no-sync` stops `uv run`
from re-installing it); restore with `uv sync`.

```bash
# Verbose output with print statements
pytest -v   # Verbose
pytest -vv  # Extra verbose
pytest -s   # Show print statements
```

## Architecture

### Package layout

```
pyproject.toml                     # virtual uv workspace root (no [project]); members + sources
packages/
├── coral-core/                    # the contract: the Plugin ABC, nothing else. Depends on nothing internal.
│   └── src/coral_core/__init__.py
├── coral-app/                     # the host: discovery, node types, graph, executor, CLI. Depends on coral-core only.
│   └── src/coral_app/
│       ├── __init__.py            # PLUGIN_GROUP, discover/load, build_function_map/build_class_map
│       ├── primitives.py          # the type table: PRIMITIVES_MAP + COLLECTION_TYPES (host-only)
│       ├── builtin_nodes.py       # the host's own functions: the list/set/dict operations
│       ├── nodeports.py           # the port table: each node type's inputs and outputs
│       ├── graph.py               # read, validate and order a workflow graph
│       ├── registry.py            # node_types.json generation (renders the port table)
│       ├── executor.py            # graph execution: walk the order, call each node
│       ├── nodestatus.py          # the per-node status markers: qualified ids + the marker files
│       └── cli.py                 # register / run subcommands; console script `coral`
├── coral-plugin-math/             # entry point `math`  -> coral_plugin_math:MathPlugin
├── coral-plugin-string/           # entry point `string`-> coral_plugin_string:StringPlugin
└── coral-plugin-phiflow/          # entry point `phiflow` -> coral_plugin_phiflow:PhiFlowPlugin (owns phiflow/jax/h5py)
```

**Dependency direction (strict):** `coral-core` depends on nothing internal; `coral-app` depends on `coral-core`;
each plugin depends on `coral-core` **and only core** (never on `coral-app`); the host never imports a plugin —
it finds them at runtime via entry-point discovery.

### Core components

1. **`coral-core`** — the shared contract, an ABC:
   ```python
   class Plugin(ABC):
       @abstractmethod
       def get_functions(self) -> dict[str, Callable]: ...
       @abstractmethod
       def get_classes(self) -> dict[str, type]: ...
   ```
   There is no `name`/`describe` — a plugin's **entry-point name** is its identity. The ABC *enforces* both
   methods (a subclass missing either cannot be instantiated).

2. **Plugins (`coral-plugin-*`)** — each subclasses `Plugin` and returns today's dict-shaped surface from
   `get_functions()` / `get_classes()`. Each declares itself under the `coral.plugins` entry-point group with its
   **class** as the target, e.g. `[project.entry-points."coral.plugins"] math = "coral_plugin_math:MathPlugin"`.
   The entry-point **name** (`math` / `string` / `phiflow`) is the identity the platform's `-p` contract uses and
   must not change. `coral-plugin-phiflow` declares `phiflow`/`jax`/`h5py` as hard dependencies.

3. **`coral-app`** — the host. Its `__init__.py` provides:
   - `PLUGIN_GROUP = "coral.plugins"`.
   - `discover() -> list[str]`: lists installed plugin names, **sorted**, **without importing** any.
   - `load(name) -> Plugin`: imports **only** that plugin, validates it resolves to a `Plugin` subclass
     (`TypeError` otherwise), instantiates it (`PluginClass()`); unknown name → `LookupError`.
   - `build_function_map(include=None, exclude=None)` / `build_class_map(...)`: same signatures as before, now
     re-backed by `discover`/`load`. `include=None` → `sorted(discover())`; names are merged in selection order
     (later wins on key collision, e.g. the `print_result` shared by math + string). An unknown name → `LookupError`.
     `build_function_map` then applies `BUILTIN_FUNCTIONS` **last**, so **a builtin name cannot be shadowed**:
     "later wins" settles a collision between two *plugins*, which are peers; a builtin is a host guarantee, and
     a plugin silently redefining `list_append` for every graph on the platform would be undebuggable from the
     graph, which names only the node type. Such a plugin declaration is ignored (silently — making it fail loud
     is a separate change). `build_class_map` is unaffected: there are no builtin classes.
   - Re-exports the two host-owned node surfaces: `PRIMITIVES_MAP` / `COLLECTION_TYPES` / `TYPE_NAMES`
     (from `coral_app/primitives.py`) and `BUILTIN_FUNCTIONS` (from `coral_app/builtin_nodes.py`).

   The rest of the host is **one job per module**, in stages (issue #23). Nothing imports backwards:
   `nodeports` knows callables but not graphs; `graph` knows graphs but not callables; `registry` and
   `executor` are two independent consumers that **do not import each other**.

   - **`nodeports.py`** (stage 2): `build_port_table(function_map, class_map, primitives)` returns
     node type -> `NodePorts(kind, inputs, outputs)` — `inputs` a list of `(name, annotation)` in
     port order, `outputs` one annotation per output port. The **single place** that derives a node's
     arity from a callable, so the registry and the executor can no longer disagree about it. A
     method's port 0 is its instance (`("self", cls)`); a missing annotation is normalised to `Any`.
     `methods_of(port_table, class_name)` lists a class's `Class.method` entries.
   - **`graph.py`** (stage 3): `Graph(nodes, edges, port_table)` and
     `Graph.from_file(path, port_table)`. **Constructing one validates it** — see
     [Graph validation](#graph-validation). Exposes `.order`, `.node(id)`, `.ports_of(id)` and
     `.inputs_of(id)` (incoming edges sorted by `target_input`, built once). Takes the port table as
     plain data, so it imports neither `inspect` nor any plugin machinery, and its tests need no
     plugin installed.
   - **`registry.py`** (stage 5): `generate_registry()` renders the port table into the platform's
     file format, `python_type_to_string()`, `save_registry_to_file(filename, plugins=...)`. Every
     decision about the *format* lives here — argument dicts, index numbering, the `[-1]`
     convention; the arity and annotations come from the port table.
   - **`executor.py`** (stage 4): `WorkflowExecutor(workflow_file, plugins=..., touch_dir=...)` —
     see [Data flow](#data-flow). Validation happens during construction, so `execute()` only walks,
     calls and stores. No `json`, no `graphlib`, no edge list — and no `pathlib`/`os` either: the
     status markers are written by `nodestatus.py`.
   - **`nodestatus.py`**: the per-node status markers — `qualified_ids(nodes)` (a pure function
     naming the files) and `NodeStatusDir` (the context manager writing them). One external
     consumer's file format, kept out of `graph.py` and `executor.py` the way `registry.py` keeps
     the registry's format out of them. Imports neither. See
     [Per-node execution status](#per-node-execution-status).

4. **`coral-app/cli.py`** — Coral-compatible CLI entry point (argparse):
   - Global `-p/--plugin` names the plugins to load (comma-separated; empty = all installed).
   - `register` subcommand → `save_registry_to_file()` (writes `node_types.json` into the cwd).
   - `run` subcommand → `WorkflowExecutor(...).execute()`, forwarding `--touch-dir` (default
     `"./"`, the cwd — see [Per-node execution status](#per-node-execution-status)).
   - Empty `-p` resolves to `discover()` (all installed), passed explicitly.
   - Exposed as the `coral` console script; wrapped by `coral-py` for the platform.

### Workflow JSON Structure

**Network Files** (e.g., `network-from-fe.json`):
Located at: `workflow.nodes` and `workflow.edges`

Nodes are **lean**: each carries its `type` and its `qualified_id` (plus `value` for primitives);
the executor infers the kind from `type`, so `node_type`/`method_name` are not part of the graph.
The `qualified_id` is required — see [Per-node execution status](#per-node-execution-status) — and is
omitted from the shapes below, which show only what decides a node's kind:
- Primitive: `{"type": "<type>", "value": <val>}`
- Function: `{"type": "<func_name>"}`
- Constructor: `{"type": "<ClassName>"}`
- Method: `{"type": "<ClassName>.<method_name>"}`

Edge format:
- `{"source": "<source_id>", "target": "<target_id>", "source_output": <idx>, "target_input": <idx>}`
- **CRITICAL**: `target_input` determines parameter ordering for function/method calls

**Registry Files** (e.g., `node_types.json`):
- Auto-generated schema describing all available node types, in the DealiiX platform format
- **Keyed by each node's `type`** (primitives by type name, functions by name, constructors by class
  name, methods by `Class.method`) — the editor looks entries up as `registry[type]`
- Each entry has:
  - `type`: the node type string (equals the entry's key)
  - `arguments`: Array with `connection_type` ("input"/"output"), `type`, and `name` (empty `[]` for primitives)
  - `inputs`: List of input indices
  - `outputs`: List of output indices (or `[-1]` for constructors/primitives)
  - `node_type`: "primitive", "function", "constructor", or "method"

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
| 3 | read, validate, order the graph | graph JSON + port table | `Graph` | `coral_app/graph.py` |
| 4 | execute | `Graph` + the maps | `results`, plus the status markers if a touch dir was given | `coral_app/executor.py`, `coral_app/nodestatus.py` |
| 5 | write the registry | port table | `node_types.json` | `coral_app/registry.py` |

1. **Discover/Load**: the host lists installed plugins (no import) and loads only the requested names.
2. **Build maps**: each loaded plugin's `get_functions()`/`get_classes()` are merged into `function_map` /
   `class_map` (selection order; later wins), then `BUILTIN_FUNCTIONS` is applied on top of `function_map`
   — so the host's own nodes are present under every selection and cannot be shadowed. Primitives come
   from the host `PRIMITIVES_MAP`. With no plugin at all, stage 1 still yields a complete surface: the
   primitives plus the 15 builtins.
3. **Describe node types**: `build_port_table()` turns the maps into one entry per node type, listing
   its input parameters and its outputs. Stages 4 and 5 both read it; neither introspects again.
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
`function` / `constructor` / `method`. The kind is decided in `nodeports.build_port_table()` by
membership in `PRIMITIVES_MAP` / `function_map` / `class_map` plus the `Class.method` split, in that
precedence order (so a dotted function name like `math.sqrt` stays a function).

**Primitive nodes** are the one special case, and they return early: the declared `type` casts the
node's `value` via `PRIMITIVES_MAP[type]` (the JSON protocol may carry it as a string), except `any`
which passes through unconverted and `none` which is `None`.

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
   a method's callable is produced by one of its own inputs and is known only at run time:

   | kind | callable | arguments |
   | --- | --- | --- |
   | function | `function_map[type]` | all the values |
   | constructor | `class_map[type]` | all the values |
   | method | `getattr(values[0], method_name)` | `values[1:]` |

3. **Call** — a plain positional call, `target(*arguments)`. The values already arrive in port order,
   which *is* parameter order, so nothing here looks at the callable's signature; `executor.py` does
   not import `inspect` at all. A bound method has already dropped `self`, so the same call works for
   all three kinds.
4. **Store** the result under the node id.

Two run-time checks survive in the executor, and both are there for the same reason: they are about
a *value*, not about wiring, so validation cannot have settled them in advance. Everything else was
verified before execution began.

| check | when | what |
| --- | --- | --- |
| **instance** | resolving a method's callable | input port 0 must really hold an instance of the named class (`isinstance(instance, class_map[class_name])`) |
| **output arity** | right after a node returns | a node declaring n > 1 outputs must have returned a tuple of exactly n |

The **output arity** check exists because the port table's arity comes from a return annotation,
which is a *claim* by the function's author. Everything downstream trusts it: the registry emits that
many sockets, checks 5 and 6 bound and type an edge by it, and step 1 above indexes with it. This is
the one place the claim meets what the function actually returned, and it is placed at the *producing*
node rather than at a consumer's edge so that it fires whether or not the offending port is wired —
an under-declared node cannot slip through by nobody reading its last output. The error names the
function whose annotation is wrong, not the graph that believed it:

```
Node 3 (phiflow_iterate) declares 3 outputs but returned a tuple of 2
Node 3 (phiflow_iterate) declares 3 outputs but returned int
```

Only n > 1 is checkable. At n == 1 a returned tuple is legitimate — that is the `-> tuple` case — so
there is nothing to compare; at n == 0 the value is unreachable anyway, since check 5 rejects every
outgoing edge of a node with no outputs. Nothing here checks the *types* of a tuple's elements; check
6 reasons about the declaration only.

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
sharing one, raise `ValueError`. This is the one place the C++ backend is not followed — it invents
`<node_id>_auto_<counter>` and warns. An invented name is not the node's identity, so a graph that
omits the field would hand the platform a timeline it cannot key back to its nodes; and note that
node ids and qualified ids are not the same thing (a node id is unique only within one graph), so
nothing derives one from the other. Every graph under `examples/` and `tests/fixtures/` therefore
carries a `qualified_id` per node, numbered progressively in declaration order.

**The mapping is built whether or not markers are written**: a graph must not become valid or
invalid depending on an unrelated flag.

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
`Start running node N [qid] (type = T)` before each node and `Node N [qid] (type = T) run` after it,
mirroring C++'s `slog_info` pair, so a traceback is always bracketed by lines naming the node.

### Graph validation

**The graph is fully validated before execution starts.** Constructing a `Graph` runs every check
below; a graph that constructs is a graph that can be executed. Because `WorkflowExecutor.__init__`
builds one, a wiring error surfaces there — never after a long PhiFlow run has already started. Each
failure raises `ValueError` naming the offending node or edge (edges by their key in the graph JSON).

In order:

1. every edge `source` and `target` names a declared node — **first**, because
   `TopologicalSorter` would otherwise silently materialise an unknown predecessor as a node;
2. every node `type` has a port-table entry;
3. per target node, the `target_input` values are exactly `{0 … n-1}` for n incoming edges — catches
   two edges on one port and a port index out of range;
4. the incoming edge count equals the type's input count — catches missing and extra connections;
5. every `source_output` names an output the source type has;
6. every edge's source annotation is compatible with its target annotation;
7. no cycles — the message names the cycle path.

**Every argument must be connected** (check 4). A default value in plugin code is *not* a way to
leave a port unwired, so the defaults in `phiflow_union`, `phiflow_iterate`,
`phiflow_plot_and_save`, `Calculator` and `StringProcessor` are unreachable from a graph. This is
long-standing behaviour, moved earlier.

**`source_output` (check 5)** — both `0` and `-1` appear on the wire for a single-output node, so
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
index: check 5 already bounds it, and duplicating that would put the same rule in two places.

**Edge type compatibility (check 6)** is deliberately narrow: it skips whenever the answer is not
certain, because wrongly refusing a good graph is worse than not checking one.

| source | target | verdict |
| --- | --- | --- |
| `Any`, or no annotation | anything | skip |
| anything | `Any`, or no annotation | skip |
| a class | the same class, or a base of it | accept |
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
every node type, except a method's `self` (which the port table synthesises from the class). Across
the three plugins and the host's builtins, 86 of 120 slots are checkable and 34 are `Any` — and the
`Any` is concentrated in one plugin:

| source | slots | `Any` | checkable |
| --- | --- | --- | --- |
| math | 28 | 1 | 27 |
| string | 8 | 1 | 7 |
| phiflow | 48 | 23 | 25 |
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
`packages/coral-plugin-phiflow/src/coral_plugin_phiflow/__init__.py` provide a simplified,
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

Three properties hold for all 15, and graphs depend on each:

- **Pure.** Every operation returns a *new* collection and never mutates its input. A node's result is
  read by every downstream consumer in an order the topological sort chooses, so in-place mutation would
  make the graph's outcome depend on that choice.
- **Fail loud.** A missing index or key raises (`IndexError` / `KeyError`); `set_remove` uses `remove`,
  not `discard`. No `None` fallbacks and no default arguments — graph check 4 requires every port to be
  wired, so a default would be unreachable.
- **No element typing.** Annotations are the bare `list` / `set` / `dict`, elements are `Any`. A generic
  alias would make graph check 6 skip the container edge as well (see the note under
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
  `outputs: [0]`); primitives also take no input but use `outputs: [-1]`. Together with `"list"` as a
  socket type that is not a registry key, these are the two platform-facing novelties to confirm in the
  editor.

Runnable examples: `coral run examples/collections/list.json` (also `set.json`, `dict.json`). The
"needs no plugin" property is asserted by `tests/test_integration.py::TestCollectionWorkflows`, which
passes `plugins=[]` — the CLI cannot express it, since an empty `-p` means *all* installed plugins.

## Key Constraints and Design Decisions

- **Edge ordering is critical**: Function/method parameter order determined by `target_input` values on edges (sorted ascending)
- **Type system**: maps Python types to the protocol's type-name strings. The table lives in
  `coral_app/primitives.py` and is **split in two**, because not every type name is a node type:
  `PRIMITIVES_MAP` holds the six *primitive node* types (`int`, `float`, `str`, `bool`, `any`, `none`)
  — a node carrying a literal in its `value` field, cast by the declared type; `COLLECTION_TYPES` holds
  `list` / `set` / `dict`, which a socket can be typed with but which **no node creates**. A collection
  is built by `list_new()` / `set_new()` / `dict_new()`, so `{"type": "list"}` in a graph is an unknown
  node type and graph check 2 rejects it. `TYPE_NAMES` is their union and is what `registry.py` renders
  from. Consequence to know: `"list"` is the first socket type string with no matching `registry[...]`
  key — see [Built-in collection nodes](#built-in-collection-nodes)
- **Node ids are decimal integers** in any graph the repo ships. The protocol keys nodes by integer:
  the reference C++ backend reads each key with `std::stoi` into an `unsigned int`, and the platform's
  exporter `parseInt`s every edge endpoint — a word id becomes `NaN`, which `JSON.stringify` writes as
  `null`, so the graph comes back with its wiring gone. `graph.py` itself takes the opposite position on
  purpose: it coerces endpoints with `str()` and treats ids as opaque, which keeps readable ids
  (`"a"`, `"b"`) available to the in-memory graphs `tests/test_graph.py` builds. The rule is therefore
  enforced on *files*, not in the loader — `tests/test_graph_ids.py` checks every graph under
  `examples/` and `tests/fixtures/`, node ids, edge keys and both endpoints of every edge. Leading
  zeros and negative ids are rejected too (`std::stoi("01")` is `1`, so `"01"` and `"1"` would name one
  node). Consequence for test data: a fixture's node names live in a `*_NODES` map in
  `tests/test_integration.py`, not in the JSON, which has no field for them
- **No cycles**: Workflow graphs must be acyclic (DAG) — `graph.py` raises `ValueError` naming the
  cycle path, using `graphlib.TopologicalSorter` (stdlib, `{node: predecessors}`)
- **Validate before executing**: every wiring error raises while the `Graph` is being constructed, so
  `WorkflowExecutor(...)` fails before the first node runs — see [Graph validation](#graph-validation)
- **One job per module**: `nodeports` knows callables but not graphs; `graph` knows graphs but not
  callables (it never imports `inspect` or a plugin); `executor` receives an already-validated graph
  (no `json`, no `graphlib`, no edge list). `tests/test_core_contract.py` enforces these boundaries
- **Lazy discovery**: `discover()` never imports a plugin; `load(name)` imports only that one. An unselected
  `phiflow` is never imported, so its heavy deps aren't paid for.
- **Fail-loud on unknown plugin**: an unknown / not-discoverable `-p` name raises `LookupError`; an
  installed-but-broken plugin raises `ImportError` at load. No silent partial state.
- **No `from __future__ import annotations`** (project-wide): it stringizes annotations, which would make
  `registry.py:python_type_to_string` see `"float"` instead of `float` and collapse every socket to `"any"`. A
  guard test (`tests/test_core_contract.py`) enforces this across `packages/*/src`.
- **Naming conventions**:
  - Functions: Use simple names in the function map (e.g., `"add"`, `"math.sqrt"`)
  - Methods: Use fully qualified names (e.g., `"Calculator.add_to_value"`)
  - Classes: Class name becomes the `type` field for constructors (e.g., `"Calculator"`)
  - Plugin entry-point names (`math` / `string` / `phiflow`) are the platform-facing identity — do not change them.
- **Type hint requirement**: All functions/methods must have type hints for proper registry generation
- **C extension limitation**: C extension classes (like `datetime`) only register constructors, not methods (due to `inspect.isfunction()` behavior) — and the constructor is a placeholder, `object.__init__`'s `*args`/`**kwargs` as two `any` ports, not the type's real arguments

## Adding a New Plugin

To add support for a new library or capability, create a **new plugin distribution** under `packages/`. Nothing
in `coral-core` or `coral-app` changes — the host discovers the plugin at runtime once it's installed.

1. **Create the package skeleton** `packages/coral-plugin-<name>/`:
   ```
   packages/coral-plugin-<name>/
   ├── pyproject.toml
   └── src/coral_plugin_<name>/__init__.py
   ```

2. **Write typed wrapper functions/classes** (type hints are required — the registry is annotation-driven; see
   the ONBOARDING guide for why `math.sqrt` needs a wrapper) and a `Plugin` subclass:
   ```python
   # src/coral_plugin_<name>/__init__.py
   from typing import Any, Dict
   from coral_core import Plugin

   def my_function(param1: float, param2: str) -> int:
       """Function description"""
       ...

   class MyClass:
       def __init__(self, x: float = 0.0): ...
       def do_thing(self, amount: float) -> float: ...

   class MyPlugin(Plugin):
       def get_functions(self) -> Dict[str, Any]:
           return {"my_function": my_function}
       def get_classes(self) -> Dict[str, Any]:
           return {"MyClass": MyClass}
   ```

3. **Declare the entry point and dependencies** in `packages/coral-plugin-<name>/pyproject.toml`:
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
   <name> = "coral_plugin_<name>:MyPlugin"

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
   (`[tool.uv.workspace] members = ["packages/*"]` already includes the directory.)

5. **Sync and regenerate the registry**:
   ```bash
   uv sync
   coral -p "<name>" register --output=/tmp/check.json
   coral -p "<name>" run my_test_graph.json
   ```
   The plugin's entry point is discovered automatically; `discover()` will list `<name>`.

**How registration works internally:**
1. Constructor nodes are generated from `__init__` signatures.
2. Method nodes are auto-generated for all public instance methods (non-underscore).
3. Methods use fully qualified names: `ClassName.method_name`.
4. First input to method nodes is always the instance.

**Limitations:**
- C extension classes (like `datetime`) only register constructors, not methods (due to `inspect.isfunction()`
  returning False for C extension methods). The constructor is a placeholder too: such a class defines no
  `__init__` of its own, so the port table reads `object`'s — `(self, /, *args, **kwargs)` — and emits two
  `"any"` sockets named `args`/`kwargs`, which no graph can wire usefully. For a real constructor and full
  method support, create a pure-Python wrapper class.

### Type Hint Requirements

The registry system requires explicit type hints:
- Use basic Python types: `int`, `float`, `str`, `bool`
- Use `Any` from `typing` for flexible types (note: has issues with `function-schema` library)
- Return type `None` indicates no output
- Missing type hints default to `"any"` in registry
- A **tuple return must declare its elements**: `Tuple[float, str]` is two output ports. Bare `Tuple`,
  `Tuple[()]` and `Tuple[Any, ...]` are rejected by `build_port_table` with a `ValueError` naming the
  function — the first two would yield *zero* ports, and the variadic form has no static arity and
  would yield a port annotated `Ellipsis`. Plain lowercase `tuple` is legal and different: **one**
  output port whose value happens to be a tuple, passed on whole. The rejection fires while the port
  table is built, i.e. at `coral register` and at every `WorkflowExecutor` construction, so one badly
  annotated function fails the host rather than yielding a wrong registry
- A function must return what its annotation declares: a node declaring n > 1 outputs returning
  anything but a tuple of exactly n raises at run time (see [Node Execution Model](#node-execution-model))
- Do **not** use `from __future__ import annotations` (see Key Constraints above)
