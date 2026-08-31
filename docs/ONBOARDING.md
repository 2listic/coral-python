# coral-python — Overview

A guide to what this project is, why it exists, how it's built, and how to extend it — for two
audiences: someone who wants to **add a CFD/scientific library** to it, and someone who wants to
**improve its internal design or its contract with the DealiiX platform**.

This complements `README.md` (setup + day-to-day commands) and `CLAUDE.md` (mechanics reference for
AI-assisted development). This document is the *story*: goals, architecture, rationale, and an honest
account of strengths and weaknesses.

*Last updated: 2026-07-21. Describes coral-python at the **local-MVP** stage — a coral-compatible backend
running graphs end-to-end locally — now restructured as a **plugin monorepo** (a `coral-core` contract, a
`coral-app` host, and one `coral-plugin-*` per capability, discovered via entry points). See
[Roadmap / deferred work](#roadmap--deferred-work) for what is still out of scope (remote/Slurm execution,
pipeline stages).*

## Contents

- [Goals & context](#goals--context)
- [Architecture](#architecture)
- [Development setup](#development-setup)
- [Use](#use)
- [Adding a new library](#adding-a-new-library-persona-a)
- [Extending internals or contracts](#extending-internals-or-contracts-persona-b)
- [Design rationale / FAQ](#design-rationale--faq)
- [Strengths & weaknesses](#strengths--weaknesses)
- [Roadmap / deferred work](#roadmap--deferred-work)

---

## Goals & context

**DealiiX platform** is a node-based visual editor: users build a graph of function calls, class
constructors, and method calls, then export it as JSON and execute it against a backend. The
original backend is **CORAL**, a C++ engine built on deal.II for finite-element simulations.

**coral-python exists as a cross-validation proof case.** If the platform's approach — a visual
node editor talking to a backend purely through a JSON protocol — is sound, it should work against
a *second, independent* engine built with different tools for a different domain (Python +
[PhiFlow](https://github.com/tum-pbs/PhiFlow) for fluid simulation, instead of C++ + deal.II for
FEM). coral-python is that second engine.

To make the comparison meaningful, coral-python doesn't invent its own protocol — it is
**coral-compatible**: it speaks the *same* CLI surface and the *same* JSON schema as the C++ CORAL
binary. From the platform's point of view, switching from the C++ backend to coral-python means
changing two settings (the executable path and the "plugin" value) and nothing else. See
[Architecture](#architecture) for exactly what that contract is.

---

## Architecture

### A plugin monorepo: core, host, plugins

The code lives in packages under `packages/*`, with a strict one-directional dependency rule:
**core → nothing internal; app → core; each plugin → core; the host never imports a plugin.**

```
                   ┌──────────────────────────────┐
                   │  coral-core                  │   the contract only: a Plugin
                   │  Plugin (ABC):               │   ABC with two @abstractmethods.
                   │    get_functions()           │   Depends on nothing internal.
                   │    get_classes()             │
                   └───────────────▲──────────────┘
                                   │ subclass
        ┌────────────────────────────────────────────────────┐
        │  coral-plugin-math    -> MathPlugin                │   each declares itself under the
        │  coral-plugin-string  -> StringPlugin              │   entry-point group "coral.plugins",
        │  coral-plugin-phiflow -> PhiFlowPlugin             │   pointing at its Plugin class
        └──────────────────────────▲─────────────────────────┘
                                   │ discover() / load(name) — lazy: list without importing;
                                   │                           import only the requested plugin
        ┌──────────────────────────▲─────────────────────────┐
        │  coral-app  (the host)                             │
        │    discover / load                                 │
        │    build_function_map() / build_class_map()        │
        │    PRIMITIVES_MAP                                  │
        └───────────────┬─────────────────────┬──────────────┘
                        │                     │
              ┌───────────────────┐ ┌───────────────────┐
              │  registry.py      │ │  executor.py      │
              │  describes nodes  │ │  runs nodes       │
              └─────────┬─────────┘ └─────────┬─────────┘
                        ▼                     ▼
                 node_types.json        graph results
```

**Discovery is lazy and via standard metadata.** Plugins declare themselves under the
`importlib.metadata` entry-point group `coral.plugins`, pointing at their `Plugin` **class**. The host's
`discover()` lists installed plugin names *without importing any*; `load(name)` imports **only** that one
plugin, checks it subclasses `Plugin` (`TypeError` otherwise), and instantiates it. An unknown name →
`LookupError`. This is what lets a plugin that was unknown when the host was built — including a third-party
one — be found and loaded purely from its installed metadata.

**The contract is an enforced ABC, not a convention.** `coral-core`'s `Plugin` uses `@abstractmethod`, so a
plugin that forgets `get_functions()` or `get_classes()` cannot even be instantiated. There is no `name`
method — the entry-point name (`math` / `string` / `phiflow`) *is* the plugin's identity, and it's the string
the platform's `-p` contract passes.

Inside the host, `registry.py` and `executor.py` **do not import each other.** Both import only from
`coral_app` (`from coral_app import PRIMITIVES_MAP, build_function_map, build_class_map` — identical line in
both files). This is deliberate: the registry's job is to *describe* what's callable; the executor's job is to
*run* it. See [Extending internals](#extending-internals-or-contracts-persona-b) for why this decoupling
matters.

### The two contracts

Everything the platform needs from coral-python reduces to two contracts:

**1. The CLI contract.** `coral` (the `coral-app` console script) exposes the same surface as the C++
`coral` binary:

```
coral -p <plugins> register [--output FILE]              # write the node registry
coral -p <plugins> run <graph.json> [--touch-dir DIR]    # execute a graph
```

`-p`/`--plugin` is repurposed: for C++ coral it's a path to a compiled plugin (`.so`); for
coral-python it's a **comma-separated list of plugin names to load** (e.g. `"math,string"`;
empty means "load every installed plugin" — see `coral_app/cli.py`'s `_resolve_plugins`, which resolves
empty to `discover()`). This is the *only* semantic difference the platform has to know about, and it's just
a string it already passes through opaquely. The `coral-py` launcher script wraps the console script so the
platform can point its `coralBinaryPath` setting straight at it (see `README.md` for the exact invocation).

`--touch-dir` is the directory `run` drops its per-node status markers into, and — as in the C++ binary —
it defaults to `"./"`, the cwd: there is no "write nothing" mode at the CLI. See
[Per-node execution status](../CLAUDE.md#per-node-execution-status) in `CLAUDE.md` for the three
markers and the `qualified_id` naming.

**2. The JSON contract.** Two JSON shapes:

- **Registry** (`node_types.json`, produced by `register`) — a dict keyed by each node's `type`
  string, one entry per primitive/function/constructor/method. This is generated by
  `coral_app/registry.py:generate_registry()`.
- **Graph** (consumed by `run`) — `{"workflow": {"nodes": {...}, "edges": {...}}, ...}`, where each
  node is *lean*: just `{"type": "...", "value": ...}` (primitives) or `{"type": "..."}`
  (everything else). No `node_type`, no `method_name` — what a node **is** follows purely from its
  `type` string: `nodeports.py` decides the kind when it builds the port table, and the executor reads
  it back as `graph.ports_of(node_id).kind`. This matches exactly what the platform exports.

### Data flow in practice

```
1. Probe:    platform runs `coral-py -p "math,string" register`
             → host discovers plugins, loads math + string (only those), merges their
               get_functions()/get_classes() and adds the host's own builtins
             → nodeports.py introspects those callables into the port table
             → registry.py renders the port table, writes node_types.json
             → platform reads it, populates the sidebar

2. Build:    user drags nodes onto the canvas, connects them,
             platform exports a lean graph.json

3. Run:      platform runs `coral-py -p "math,string" run graph.json`
             → the same port table is rebuilt from the same plugin selection
             → graph.py reads graph.json, validates it against the port table
               (a bad graph fails here, before any node runs) and topologically sorts it
             → executor.py walks that order, calling the real Python functions/classes
             → results printed to stdout (captured as the run log)
```

### How node types are read from signatures — `inspect.signature`, and whether it should stay

The registry is entirely **annotation-driven**, and the mechanism that reads those annotations is the standard
library's `inspect.signature`. It's worth understanding it precisely, because it's the single fact that
explains why most libraries need a wrapper.

**How it works.** `nodeports.py` calls `inspect.signature(...)` on each callable — a function
(`_function_ports`), a constructor (`_constructor_ports`, falling back to `cls.__init__` for a C extension
type), or a method (`_method_ports`). It walks `sig.parameters` (ordered, each carrying a `.annotation`) plus
`sig.return_annotation`, and stores the result as that node type's **port table** entry: one
`(name, annotation)` per input, one annotation per output. `registry.py` then renders those annotations through
`python_type_to_string`, which maps each against `TYPE_NAMES` — the six primitive node types (`int`, `float`,
`str`, `bool`, `any`, `none`) plus the three collections (`list`, `set`, `dict`), which are socket type names
without being node types. Three behaviours fall out of this:

- A **missing parameter** annotation becomes `"any"` — usable, just loosely typed.
- A **missing return** annotation produces **no output socket at all** (`_outputs_from_return` returns `[]`),
  so the node becomes a dead end. A `Tuple[...]` return, by contrast, becomes one output socket per element —
  and must declare those elements, since bare `Tuple`, `Tuple[()]` and `Tuple[Any, ...]` state no arity and are
  rejected outright. Plain lowercase `tuple` is a *single* output whose value happens to be a tuple.
- Because the arity is a **claim** by the annotation's author, the executor confronts it with reality: a node
  declaring more than one output must return a tuple of exactly that many, or it raises (issue #31).

The port table is the single place this introspection happens. `registry.py` and `executor.py` are two
independent consumers that both read it and neither introspects again — which is what closed the
"convention, not contract" seam that used to exist here, when the two files each called `inspect.signature`
for themselves and could disagree about a node's arity. `executor.py` no longer imports `inspect` at all.

**Why it was chosen.** It's in the standard library (zero dependencies), and a single call yields ordered
parameters, defaults, and the return annotation in one uniform shape across functions, methods, and
constructors. For an annotation-driven registry it's the minimal thing that works, and it is entirely
sufficient for the code we actually own — our own typed wrappers and pure-Python annotated classes such as
`Calculator` register with no adapter at all.

**Its honest limit.** `inspect.signature` reads only the *raw* annotations that exist on the object at runtime.
That is a hard boundary in two directions, and both are common:

- **C-implemented code carries no runtime annotations.** Everything in `math`, most of `numpy`, and the fast
  paths of scientific libraries introspect to *empty* parameters and *empty* return — so they'd register with
  `"any"` inputs and no output.
- **Modern pure-Python libraries stringize their annotations.** With `from __future__ import annotations`
  (PEP 563), `inspect.signature` returns the *string* `"float"` rather than the type `float`, and
  `python_type_to_string`'s identity check against `TYPE_NAMES` misses it → `"any"`.

We measured how much of the real ecosystem this rules out, and the answer is sobering: across **751 public
callables** in `numpy` (461), `jax` (98), and `phi.flow` (192), **zero** are directly registrable into a clean,
wireable node — `numpy` because it's C (no annotations), `jax` because it uses PEP 563 (77 of its annotated
callables come back as strings), `phi.flow` because its types aren't primitives. Scanning every third-party
top-level module installed here, only three exposed *any* natively-usable callable, and those were incidental
helpers (`pyparsing.col`, `opt_einsum.get_symbol`, `iniconfig.iscommentline`). **The practical conclusion:
hand-written, type-hinted wrappers are the rule, not a corner case** — see
[why `math.sqrt` needs a wrapper](#why-does-mathsqrt-need-a-wrapper-cant-we-load-python-functions-dynamically).

**The alternatives, and our opinion on each.**

- **`typing.get_type_hints()`** — resolves PEP 563 string annotations and forward references that raw
  `inspect.signature` leaves as strings. This is a cheap, low-risk change that would unlock the whole class of
  modern annotated pure-Python libraries (it would, for instance, make `jax`'s stringized signatures readable).
  *Our take: the one improvement worth doing first.* It doesn't fix C code (there are still no annotations to
  resolve) and is still bounded by the six-primitive map, but it removes the most common avoidable failure.
- **Static AST parsing of source files** — extracts signatures without importing, dodging import side effects.
  Heavier machinery, and still annotation-dependent (it reads the same hints). *Not worth it at this scale.*
- **Explicit decorator / manual schema registration** — precise and introspection-free, but it trades every
  signature for hand-written boilerplate. *Only worth it if we deliberately need to register many
  un-annotatable callables.*
- **`.pyi` stub reading** — the *only* route that could recover types for C functions (`numpy` et al.), since
  that information lives solely in stubs. But it's high-complexity and fragile (stub discovery, version skew).
  *Probably not worth it; a hand-written wrapper is simpler and more honest about intent.*

**Bottom line.** Keep `inspect.signature` for now — it's simple and fully sufficient for the code we own. If we
later want more external libraries to "just work," the pragmatic path is `get_type_hints()` plus a richer type
map, in that order. But wrappers remain unavoidable for C and array libraries no matter which reader we choose:
that's a property of the Python ecosystem (no runtime types for compiled code), not a shortcoming of this
design.

### How a lean graph becomes results — ordering, and recovering what a node is

Two questions have to be answered before a lean graph can run: *in what order*, and *what is each node*.
Neither is answered by `executor.py` — issue #23 moved both upstream of it, which is why the executor is now
only a walk-and-call loop.

**Execution order.** `graph.py:_build_order()` uses the standard library's
`graphlib.TopologicalSorter`, handed `{node: predecessors}` — the inverse of an adjacency list. A cycle raises
`ValueError` naming the cycle path. Two guarantees fall out: a node runs only after all its inputs exist, and
the order is **deterministic** — each ready batch is `sorted()` before being emitted, so the order is a
function of the graph rather than of JSON key order. (Those ready batches are also the natural hook for
executing independent branches concurrently, which nothing does today.)

**Recovering what a node is.** Because lean nodes carry only `{type, value?}`, something has to recover each
node's *kind*. `nodeports.build_port_table()` decides it once per node **type** — not per node — by membership,
in this precedence order:

```
primitive     type in PRIMITIVES_MAP
function      type in function_map
constructor   type in class_map
method        type splits on the last "." into a known class + a method name
```

Precedence matters: a dotted *function* name such as `math.sqrt` is tested against `function_map` before the
`Class.method` split is attempted, so it stays a function even if some class were also called `math`. The
executor reads the answer back as `graph.ports_of(node_id).kind` and never re-derives it.

Two things worth being precise about:

- The port table records a node type's **argument shape** too, not just its kind: one `(name, annotation)` per
  input port, one annotation per output. So nothing downstream introspects a second time — the executor binds
  a node's inputs with a plain positional call (`target(*arguments)`, no `inspect` import at all), because the
  values arrive in port order, which *is* parameter order.
- Cost is paid per node *type* at startup rather than per node at run time, and lookups during the walk are
  hash-map hits. `graph.py` likewise buckets incoming edges by target once, in `__init__`, so no node rescans
  the edge list. A run is linear in nodes plus edges.

---

## Development setup

coral-python is a [uv **workspace**](https://docs.astral.sh/uv/concepts/projects/workspaces/) — a monorepo
of packages under `packages/*`, wired together by a virtual root `pyproject.toml` + `uv.lock`:

```bash
uv sync          # creates .venv, installs the whole workspace (incl. the dev group) from the lockfile
```

That installs every workspace package **editable**, plugins included, so entry-point discovery finds them
straight from the checkout: developing needs `uv` only, never `pip`, and never a separate plugin install.
Then either activate the venv (`source .venv/bin/activate`) or prefix commands with `uv run`. See
`README.md` for the full setup section, dependency management (`uv add --package …`), and running the test
suite.

**The wheel is the boundary between the two audiences.** Everything in this guide is the developer side:
uv, editable installs, the workspace. End users never touch uv — a developer runs
`uv build --all-packages --wheel --out-dir dist` and ships `dist/`, and they install it with
`pip install --find-links dist coral-app` plus whichever `coral-plugin-*` they want. See
[Installation in `README.md`](../README.md#installation). Building wheels is a distribution step, not part
of the development loop.

---

## Use

```bash
# Generate the registry for one or more plugins (writes node_types.json in the cwd)
uv run coral -p "math" register

# Run a graph with those plugins loaded
uv run coral -p "math" run tests/fixtures/valid_workflows/network-from-fe-math.json
```

Through the launcher (what the platform actually invokes):

```bash
./coral-py -p "math,string,phiflow" register
./coral-py -p "math,string,phiflow" run graph.json
```

`coral-py` runs the `coral` console script inside this workspace's `.venv` via `uv run --project`,
**without changing the working directory** — so `register`'s output and the platform's configured working
directory stay consistent with what the platform expects (see the comments in `coral-py`).

On the platform side: Settings → Execution Mode → **Local / Coral**, with the *Coral binary path*
pointed at `coral-py` and the *Coral plugin path* field holding the plugin list (that field accepts
free text precisely to support this — see dealiiX-platform PR #209). Then **Save & Sync** probes the
registry, and **Execute** runs a graph.

---

## Adding a new library (Persona A)

You want to add support for a CFD/scientific library other than PhiFlow — say, a different fluid
solver, a mesh library, or a numerics package.

### The steps

You create a **new plugin distribution** under `packages/`. Nothing in `coral-core` or `coral-app`
changes — the host discovers your plugin at runtime once it's installed.

1. **Create the package skeleton** `packages/coral-plugin-mycfd/`:

   ```
   packages/coral-plugin-mycfd/
   ├── pyproject.toml
   └── src/coral_plugin_mycfd/__init__.py
   ```

2. **Write typed wrapper functions/classes** (not raw calls into the library) and a `Plugin`
   subclass. See
   [why wrapping is necessary](#why-does-mathsqrt-need-a-wrapper-cant-we-load-python-functions-dynamically)
   below — the short version is: the registry can only produce a useful node if the function has
   type-annotated parameters and a type-annotated return value. The `Plugin` ABC *enforces* both
   methods (forget one and the class can't be instantiated):

   ```python
   # src/coral_plugin_mycfd/__init__.py
   from typing import Any, Dict
   from coral_core import Plugin
   from mycfd import Solver  # the real library — a hard dependency of this plugin (see step 3)

   def create_solver(resolution: int) -> Any:
       """Wrap Solver's constructor with an explicit, registry-friendly signature."""
       return Solver(resolution=resolution)

   class MyCFDPlugin(Plugin):
       def get_functions(self) -> Dict[str, Any]:
           return {"create_solver": create_solver}
       def get_classes(self) -> Dict[str, Any]:
           return {}
   ```

3. **Declare the entry point and dependencies** in `packages/coral-plugin-mycfd/pyproject.toml`. The
   entry-point **name** (`mycfd`) is what `-p` references; the target is your `Plugin` **class**. Because
   the plugin *declares* the real library as a hard dependency, installing the plugin guarantees it's
   importable — a broken install fails loud with `ImportError` (there is **no** `try/except AVAILABLE`
   guard; lazy discovery already means an unselected plugin is never imported):

   ```toml
   [build-system]
   requires = ["hatchling"]
   build-backend = "hatchling.build"

   [project]
   name = "coral-plugin-mycfd"
   version = "0.0.0"
   requires-python = ">=3.12"
   dependencies = ["coral-core", "mycfd"]

   [project.entry-points."coral.plugins"]
   mycfd = "coral_plugin_mycfd:MyCFDPlugin"

   [tool.hatch.build.targets.wheel]
   packages = ["src/coral_plugin_mycfd"]
   ```

4. **Cross-link the package** in the root `pyproject.toml` so `uv sync` installs it from the workspace
   (`[tool.uv.workspace] members = ["packages/*"]` already covers the directory):

   ```toml
   [tool.uv.sources]
   coral-plugin-mycfd = { workspace = true }
   ```

5. **Sync, then regenerate and check the registry**, then run a graph:

   ```bash
   uv sync
   uv run coral -p "mycfd" register --output=/tmp/check.json
   # inspect /tmp/check.json — every function/class you exposed should have a sensible
   # arguments/inputs/outputs shape, not everything collapsed to "any"
   uv run coral -p "mycfd" run my_test_graph.json
   ```

   `discover()` now lists `mycfd`; no host code changed.

> **Do not add `from __future__ import annotations`** to any plugin (or host) module. It stringizes
> annotations, which makes the registry read `"float"` instead of the type `float` and collapse every
> socket to `"any"`. A guard test (`tests/test_core_contract.py`) enforces this across `packages/*/src`.

### Why does `math.sqrt` need a wrapper? Can't we load Python functions dynamically?

This comes up immediately once you look at `coral-plugin-math` — `math.sqrt` isn't registered directly;
instead there's a `math_sqrt(x: float) -> float` wrapper that calls it. The reason is structural,
not stylistic:

The registry (`registry.py:generate_registry`) is **annotation-driven**. For every parameter and
return value it calls `inspect.signature(func)` and converts the annotation to a protocol type
string via `python_type_to_string`:

```python
def python_type_to_string(py_type) -> str:
    # Handle empty/missing annotations
    if py_type is inspect.Signature.empty or py_type is None:
        return _TYPE_NAME_OF[Any]
    ...
```

A missing annotation becomes `"any"`. Worse, for **return** values,
`nodeports.py:_outputs_from_return` treats a missing annotation as *no output socket at all*:

```python
if (return_annotation is not None
    and return_annotation is not type(None)
    and return_annotation is not inspect.Signature.empty):
    return [return_annotation]      # one output port
return []                           # <- missing/None annotation → zero outputs
```

`math.sqrt` is a C builtin (`builtin_function_or_method`). Even where `inspect.signature` succeeds
on it, the parameters and return carry **no type annotations** — that information simply doesn't
exist at runtime for C-implemented functions; it lives only in `.pyi` stub files, which nothing here
reads. Registering `math.sqrt` directly would therefore produce a node with an `"any"` input and
**no output socket** — impossible to wire into anything downstream.

The wrapper is the smallest fix: it supplies the annotations Python's own runtime introspection
can't recover, and it's also a convenient place for logging and type coercion (e.g. converting a
NumPy scalar back to a Python `float`). This is a real, structural constraint — not a stopgap —
whenever you're wrapping a C extension or an unannotated library.

**When you don't need a wrapper:** if the function or class is pure Python *and already carries
type hints*, register it directly — no wrapper required. That's exactly what `Calculator` in
`coral-plugin-math` does: its `__init__` and methods are annotated Python, so `registry.py` introspects
them without any adapter.

---

## Extending internals or contracts (Persona B)

You want to change how coral-python works internally, or evolve its contract with the platform.

### The decoupling is real, and it's your extension point

Because `registry.py` and `executor.py` never import each other and both consume the host surface
only through `build_function_map`/`build_class_map`/`PRIMITIVES_MAP`, you can rewrite the entire
discovery/loading layer in `coral_app/__init__.py` — a different discovery strategy, eager vs. lazy
loading, passing a host context into `PluginClass(...)`, whatever — and both the registry generator and
the executor keep working *unchanged*, as long as:

1. `build_function_map(include=...)` / `build_class_map(include=...)` keep returning
   `{name: callable}` / `{name: class}` dicts, and
2. the JSON shape each side produces/consumes stays `{type, arguments, inputs, outputs, node_type}`
   for registry entries and `{type, value?}` for lean graph nodes.

That's a genuinely useful seam: it means "improve the registry's type system" and "improve how
plugins are discovered/loaded" are separable projects. The plugin *contract* itself (`coral-core`'s
`Plugin` ABC) and the entry-point group name (`coral.plugins`) are the one part that's public API —
once real third-party plugins exist, treat both as stable.

**The cost of that decoupling:** it's enforced by *convention*, not by a shared interface or test
that pins both sides together. `registry.py` and `executor.py` **independently** encode the same
assumptions — e.g. that a dotted name like `"math.sqrt"` is a function, not a method (see the
comment in `executor.py:_classify`: *"functions checked before the split so dotted names like
`math.sqrt` resolve as functions, not methods"*), and that a method's `self` argument is always
input index 0. Nothing checks that a change to one side doesn't silently break the other's
assumptions — if you touch this boundary, update both and re-run the full suite (`uv run pytest`).

### Concrete extension points

- **Richer type system.** Nine type names round-trip through the registry: the six `PRIMITIVES_MAP`
  node types plus `list`/`set`/`dict` from `COLLECTION_TYPES` (issue #25, which also demonstrated that a
  type name need not be a node type). Every other annotation — a domain class, a parameterised generic
  like `List[int]`, a non-primitive tuple element — still collapses to `"any"`. A richer scheme (e.g.
  registering domain class names as their own protocol types, the way method `self` arguments already
  use the class name) would give more precise sockets and better validation on the canvas.
- **Lazy plugin import (done).** Entry-point discovery already imports only the plugins named in
  `-p`: `discover()` enumerates names without importing, and `load(name)` imports just that one. An
  unselected `phiflow` never triggers the PhiFlow/JAX import chain. (This was a weakness of the old
  `definitions/` layer, now resolved by the plugin architecture.)
- **Per-node execution status (done).** `--touch-dir` now emits one empty
  `<qualified_id>.running` / `.succeeded` / `.failed` per node as the graph runs, which is what
  drives the platform's live node highlighting (issue #30). The convention is `coral_app/nodestatus.py`'s
  — the executor gained one `with` statement and no filesystem import. The C++ backend was read
  rather than guessed at, and it settled four things worth knowing before touching this: the flag
  defaults to the cwd, every node is a task (primitives included), `qualified_id` is optional with a
  `<node_id>_auto_<counter>` fallback, and a failed touch mid-run is not fatal. Details and the one
  deliberate divergence — we do not wrap the failing node's exception — are in
  [Per-node execution status](../CLAUDE.md#per-node-execution-status).
*(Two entries that used to sit here — "enforcing the registry/executor convention" and "linear-time
execution" — were resolved by issue #23. The port table is now the single source of a node type's kind and
arity, which both `registry.py` and `executor.py` read and neither re-derives, and `tests/test_core_contract.py`
enforces that boundary; ordering moved to `graphlib.TopologicalSorter` and incoming edges are bucketed once. See
[How a lean graph becomes results](#how-a-lean-graph-becomes-results--ordering-and-recovering-what-a-node-is).)*

---

## Design rationale / FAQ

### Why does `math.sqrt` need a wrapper? Can't we load Python functions dynamically with no manual wrapping?

Answered in full [above](#why-does-mathsqrt-need-a-wrapper-cant-we-load-python-functions-dynamically).
Short version: the registry is annotation-driven, and Python doesn't expose runtime type
annotations for C-implemented functions — there's nothing to introspect. Pure Python functions and
classes *with* type hints (like `Calculator`) need no wrapper at all.

### Does the registry/executor decoupling really let someone rewrite the discovery layer under the same contract?

Yes — see [Extending internals](#the-decoupling-is-real-and-its-your-extension-point) above. It's a
genuine architectural property (verified: neither module imports the other; both only touch
`coral_app`'s public surface), with one honest caveat: the split *between `registry.py` and
`executor.py`* is convention-based, not contract-enforced, so changes on one side need a matching check
on the other. (The *plugin* contract, by contrast, is now an enforced ABC — see below.)

### Why discover plugins via entry points instead of a `_MODULES` dict in one package?

The earlier design kept a hardcoded `_MODULES` dict in a `definitions/__init__.py`, aggregating sibling
modules that each satisfied a *duck-typed* `get_functions()`/`get_classes()` contract. That's a fine idiom
at small scale, but it has two structural limits: every capability had to be a sibling module *inside one
package* (so nothing could be installed independently or come from a third party), and the contract was
enforced only by convention.

The plugin architecture removes both limits:
- **Discovery is via stdlib `importlib.metadata` entry points** (group `coral.plugins`). Any installed
  distribution that declares an entry point is found — including one that didn't exist when the host was
  built. The host reads standard metadata; a plugin never writes host-owned files or runs post-install
  hooks. (Rejected alternatives: path-scanning + `inspect`, namespace-package scanning, and
  `pluggy`/`stevedore` — which just wrap entry points. Canonical stdlib wins.)
- **The contract is an ABC** (`coral_core.Plugin`), not a `typing.Protocol` or a bare `register()` hook, so
  `@abstractmethod` *enforces* that a plugin implements both methods. The entry point resolves to the
  **class**; the host instantiates it (`PluginClass()`), which is the natural place to later inject a
  host-provided context object.

Two things worth knowing if you work in `coral_app/__init__.py`:
- `build_function_map` and `build_class_map` share a small `_selected(include, exclude)` helper that
  resolves the name list (`include=None` → `sorted(discover())`, then `exclude` applied). Each then loads
  the selected plugins and merges their maps.
- Because merging calls `.update()` into a shared dict in selection order, if two plugins expose the same
  key (today, `print_result` is in both `coral-plugin-math` and `coral-plugin-string`) the later one
  silently wins. Harmless today since the duplicate is identical, but worth knowing before adding a
  colliding name. The "all" order is `sorted(discover())`, so it's deterministic.
- `BUILTIN_FUNCTIONS` is applied **after** that merge, so the host's own nodes are never shadowed. That
  is a different rule from the one above, on purpose: two plugins are peers and neither has a claim to
  precedence, whereas a builtin is a promise the host makes to every graph. See the next entry.

### Why are the list/set/dict operations in the host rather than a plugin?

Because they are not a capability, they are vocabulary. A plugin is how you add *a library* — PhiFlow,
numpy, your solver. But "put a value in a list" is something every graph might need regardless of which
libraries are installed, and making it a plugin would mean a graph is portable only if the operator
remembered to install `coral-plugin-collections`. The host already ships primitives on exactly this
reasoning; the collections are the same argument one level up, so they live in
`coral_app/builtin_nodes.py` next to `primitives.py`.

The consequence is the precedence rule above: since a builtin is a guarantee rather than a contribution,
a plugin declaring `list_append` is ignored rather than winning. A graph names only node types, so a
plugin that silently redefined one would produce a wrong answer with nothing in the graph to point at.

**Why bare `list`, and not a `CoralList` wrapper class?** A wrapper would have been the tidier object
model — real methods, a real constructor, no 15 free functions. It was rejected because of what crosses
the wire *between* a builtin and a plugin. A `CoralList` is not a `list`, so the moment a plugin function
wants `List[float]`, or returns one, you need a conversion node in the graph. The direction that hurts is
the plugin *producing* a collection: a plugin author would have to import a host type to hand back
something the collection nodes can consume, and the host↔plugin dependency only runs one way. With bare
builtins, `list_get` hands a plugin function a genuine Python float out of a genuine Python list, and
nothing is converted — see `tests/fixtures/valid_workflows/network-collections-math.json`, which wires
`list_get` straight into the math plugin's `add`.

The cost of that choice is that `list`/`set`/`dict` cannot be registered as *classes* even if we wanted
to: `inspect.signature(list)` is `(iterable=(), /)`, one mandatory port, so an empty-list constructor node
would fail graph check 4; `list.append` mutates and returns `None`, so it would have no output port; and
being C extension types they expose no introspectable methods at all. Free functions are not a stylistic
preference here, they are the only thing that works.

---

## Strengths & weaknesses

**Strengths**

- Clean separation with a real, verifiable decoupling: a `coral-core` contract, a `coral-app` host, and
  independently installable `coral-plugin-*` distributions; inside the host, `registry` and `executor`
  stay decoupled (describe vs. run).
- **Enforced plugin contract.** `coral-core.Plugin` is an ABC — a plugin that omits `get_functions()` or
  `get_classes()` can't even be instantiated. No duck typing.
- **Lazy, standards-based discovery.** Plugins are found via `importlib.metadata` entry points and
  imported only when selected, so an unused `phiflow` never pays its import cost — and third-party plugins
  can be added purely by installing them.
- Genuinely coral-compatible: same CLI surface, same JSON schema as the C++ backend — the platform
  needs zero backend-specific code to drive it.
- The lean, type-keyed graph protocol matches the platform's current export format exactly (no
  adapter needed on the platform side).
- Small, well-tested surface: **100 passing tests** covering the contract, discovery/loading, registry
  generation (with byte-level golden pins), and execution.

**Weaknesses**

- **Lossy type system** — only six primitive types round-trip through the registry; everything
  else becomes `"any"`, which weakens connection validation on the canvas.
- **Annotation asymmetry** — a missing parameter annotation becomes `"any"` (still usable), but a
  missing return annotation produces *no output socket* (the node becomes a dead end). Easy to trip
  over when writing a new wrapper.
- **C-extension methods are silently dropped.** `_add_methods`'s `inspect.isfunction` check filters
  out methods of C-implemented classes (e.g. `datetime`); only their constructors register. Wrapping
  in a pure-Python class is the only workaround.
- **Convention, not contract, between `registry.py` and `executor.py`** (see above) — they independently
  encode the same `type`-classification assumptions. The *plugin* contract is now ABC-enforced, but this
  internal host seam is still convention-based — a latent risk for future changes.
- **Manual-wrapping boilerplate** is the price of the annotation-driven registry; it doesn't scale
  to "wrap an entire large library" without some repetition.

---

## Roadmap / deferred work

Not part of the current local MVP; tracked for later:

- Remote execution (SSH + Slurm), matching the platform's remote backend mode.
- Pipeline stages (coral-python as one stage in a multi-stage DAG).
- Promoting coral-python from a workspace folder to a git submodule of the platform repo, once it's
  containerized to simulate a cluster.
