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
- [Installation](#installation)
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
        │    discover / load / load_all                      │
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
empty means "load every installed plugin" — see `coral_app/cli.py`'s `_resolve_modules`, which resolves
empty to `discover()`). This is the *only* semantic difference the platform has to know about, and it's just
a string it already passes through opaquely. The `coral-py` launcher script wraps the console script so the
platform can point its `coralBinaryPath` setting straight at it (see `README.md` for the exact invocation).

**2. The JSON contract.** Two JSON shapes:

- **Registry** (`node_types.json`, produced by `register`) — a dict keyed by each node's `type`
  string, one entry per primitive/function/constructor/method. This is generated by
  `coral_app/registry.py:generate_registry()`.
- **Graph** (consumed by `run`) — `{"workflow": {"nodes": {...}, "edges": {...}}, ...}`, where each
  node is *lean*: just `{"type": "...", "value": ...}` (primitives) or `{"type": "..."}`
  (everything else). No `node_type`, no `method_name` — the executor infers what a node **is**
  purely from its `type` string (see `coral_app/executor.py:_classify`). This matches exactly what the
  platform exports.

### Data flow in practice

```
1. Probe:    platform runs `coral-py -p "math,string" register`
             → host discovers plugins, loads math + string (only those),
               registry.py introspects their get_functions()/get_classes()
             → writes node_types.json
             → platform reads it, populates the sidebar

2. Build:    user drags nodes onto the canvas, connects them,
             platform exports a lean graph.json

3. Run:      platform runs `coral-py -p "math,string" run graph.json`
             → executor.py loads graph.json, classifies each node by `type`,
               topologically sorts, and calls the real Python functions/classes
             → results printed to stdout (captured as the run log)
```

### How the registry reads signatures — `inspect.signature`, and whether it should stay

The registry is entirely **annotation-driven**, and the mechanism that reads those annotations is the standard
library's `inspect.signature`. It's worth understanding it precisely, because it's the single fact that
explains why most libraries need a wrapper.

**How it works.** `registry.py` calls `inspect.signature(...)` on each callable — a function
(`_add_function_node`), a constructor (`_add_constructor`, on `cls.__init__`), or a method (`_add_methods`). It
then walks `sig.parameters` (ordered, each carrying a `.annotation`) plus `sig.return_annotation`, and passes
every annotation through `python_type_to_string`, which maps it against the six-entry `PRIMITIVES_MAP`
(`int`, `float`, `str`, `bool`, `any`, `none`). Two behaviours fall out of this:

- A **missing parameter** annotation becomes `"any"` — usable, just loosely typed.
- A **missing return** annotation produces **no output socket at all** (`_process_return_type` returns `[], []`),
  so the node becomes a dead end. A `Tuple[...]` return, by contrast, becomes one output socket per element.

`executor.py` calls `inspect.signature` independently (when binding a function, constructor, or method node) —
the two files never share a signature helper, which is the "convention, not contract" seam described under
[Extending internals](#extending-internals-or-contracts-persona-b).

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
  `python_type_to_string`'s identity check against `PRIMITIVES_MAP` misses it → `"any"`.

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

### How the executor runs a graph — execution order and `_classify`

Two mechanisms in `executor.py` turn a lean graph into results.

**Execution order.** `get_execution_order()` is a topological sort (Kahn's algorithm): it builds an adjacency
list plus an in-degree count from the edges, seeds a queue with every zero-in-degree node, and drains it,
decrementing downstream in-degrees as it goes. If the emitted order is shorter than the node count there's a
cycle, and it raises. The guarantee this buys: a node runs only after all its inputs exist, while independent
branches have no defined relative order (any valid topological order is fine).

**Node classification.** Because lean nodes carry only `{type, value?}`, the executor has to recover what each
node *is* before it can run it. `_classify(type_str)` does exactly that, and it's deliberately cheap — a few
hash-map membership tests against maps built **once** in `__init__`, so it's effectively **O(1) per node** and
never a bottleneck:

```python
if type_str in self.primitives_map: return "primitive"    # O(1)
if type_str in self.function_map:   return "function"      # O(1)
if type_str in self.class_map:      return "constructor"   # O(1)
if "." in type_str and type_str.rsplit(".", 1)[0] in self.class_map:
    return "method"                                        # one split + O(1)
```

Two things worth being precise about:

- `_classify` recovers only the node's *kind*, not its argument shape. Parameter names and order are re-derived
  at call time with `inspect.signature(func | __init__ | method)` — the same reader the registry uses — and the
  inputs are then bound as kwargs. That per-node `inspect.signature` call is cheap but not cached.
- The only mildly non-linear parts live elsewhere, and neither matters at today's graph sizes: the topological
  sort uses a list as a queue (`queue.pop(0)` is O(n)), and each node rescans the full edge list to find its
  incoming edges (`[e for e in self.edges if e["target"] == node_id]`, O(V·E) overall). Swapping in a
  `collections.deque` and pre-bucketing edges by target would make a whole run linear — a clean, low-risk
  [Persona B](#extending-internals-or-contracts-persona-b) win if graphs ever grow large.

---

## Installation

coral-python is a [uv **workspace**](https://docs.astral.sh/uv/concepts/projects/workspaces/) — a monorepo
of packages under `packages/*`, wired together by a virtual root `pyproject.toml` + `uv.lock`:

```bash
uv sync          # creates .venv, installs every workspace package editable (incl. the dev group)
```

Then either activate the venv (`source .venv/bin/activate`) or prefix commands with `uv run`. See
`README.md` for the full setup section, dependency management (`uv add --package …`), and running the test
suite.

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
pointed at `coral-py` and the *Coral plugin path* field holding the module list (that field accepts
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
        return _REVERSE_PRIMITIVES_MAP[Any]
    ...
```

A missing annotation becomes `"any"`. Worse, for **return** values, `_process_return_type` treats a
missing annotation as *no output socket at all*:

```python
if (return_annotation is not None
    and return_annotation != type(None)
    and return_annotation != inspect.Signature.empty):
    return [_create_output_argument(return_annotation)], [param_idx]
return [], []   # <- missing/None annotation → zero outputs
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

- **Richer type system.** Only the six `PRIMITIVES_MAP` types (`int`, `float`, `str`, `bool`, `any`,
  `none`) round-trip through the registry; every other annotation (a domain class, `list`, a
  non-primitive tuple element) collapses to `"any"`. A richer scheme (e.g. registering domain class
  names as their own protocol types, the way method `self` arguments already use the class name)
  would give more precise sockets and better validation on the canvas.
- **Lazy plugin import (done).** Entry-point discovery already imports only the plugins named in
  `-p`: `discover()` enumerates names without importing, and `load(name)` imports just that one. An
  unselected `phiflow` never triggers the PhiFlow/JAX import chain. (This was a weakness of the old
  `definitions/` layer, now resolved by the plugin architecture.)
- **Per-node execution status.** The CLI accepts `--touch-dir` for compatibility with the platform's
  live per-node status feature, but doesn't yet write anything there — `executor.py` would need to
  emit a status file per node as it executes.
- **Enforcing the registry/executor convention.** A shared test (or a single source of "how to
  classify a `type` string") that both `registry.py` and `executor.py` are checked against would
  remove the "convention, not enforcement" risk described above.
- **Linear-time execution.** The executor's topological sort uses a list as a queue and each node rescans the
  full edge list for its inputs (see [How the executor runs a graph](#how-the-executor-runs-a-graph--execution-order-and-_classify)).
  A `collections.deque` plus edges pre-bucketed by target makes a whole run linear — not needed at today's
  sizes, but a clean win before scaling to large graphs. (Note: `_classify` itself is already O(1) per node.)

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
- Per-node execution status via `--touch-dir` (see [Extending internals](#concrete-extension-points)).
- Promoting coral-python from a workspace folder to a git submodule of the platform repo, once it's
  containerized to simulate a cluster.
