# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Coral for Python** is a workflow execution system that processes computational graphs defined in JSON format. The system supports four types of nodes:
- **Primitive nodes**: Hold constant values (int, float, string, bool, any)
- **Function nodes**: Execute Python functions with typed inputs and outputs
- **Constructor nodes**: Instantiate Python classes
- **Method nodes**: Call instance methods on objects created by constructor nodes

The project uses PhiFlow for physics simulations and numerical computing.

The repo is a **uv workspace / monorepo**: a small set of independently installable distributions
under `packages/*`. A minimal contract package (`coral-core`) defines a `Plugin` ABC; the host
(`coral-app`) discovers and loads plugins at runtime via `importlib.metadata` entry points; each
capability (`math`, `string`, `phiflow`) is its own `coral-plugin-*` distribution. See
[Package layout](#package-layout) below.

> For the narrative — goals, architecture rationale, the two contracts with the DealiiX platform, and how to
> extend the project — see [`docs/ONBOARDING.md`](docs/ONBOARDING.md) (Italian: `docs/ONBOARDING.it.md`). This
> `CLAUDE.md` is the mechanics reference; `README.md` covers setup and commands.

## Development Commands

### Environment Setup

This is a uv **workspace** (virtual root `pyproject.toml` + `uv.lock`); `requirements.in` / `requirements.txt`
are legacy reference only.

```bash
# Create .venv and install every workspace package editable (incl. the dev group) from the lockfile
uv sync

# Then activate, or prefix commands with `uv run` (e.g. `uv run coral run`)
source .venv/bin/activate  # Linux/Mac
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

### Running Workflows

`coral` is a coral-compatible CLI (the `coral-app` console script, `coral_app.cli:main`): a global
`-p/--plugin` option (comma-separated plugin names; empty = all installed) plus `register` / `run`
subcommands. `-p/--plugin` must precede the subcommand.
```bash
# Run a workflow graph (default file network-from-fe.json, all installed plugins)
coral run
coral run path/to/workflow.json
coral -p "math" run path/to/workflow.json
coral -p "math,string,phiflow" run path/to/workflow.json

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

### Running Standalone PhiFlow Simulations
```bash
# Run a PhiFlow simulation directly (not through workflow system)
python phi_flow/one_obstacle_absorb.py
python phi_flow/multiple_obstacles.py
# Check the generated .mp4 or .gif output file in phi_flow/ directory
```

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
├── coral-app/                     # the host: discovery, registry, executor, CLI. Depends on coral-core only.
│   └── src/coral_app/
│       ├── __init__.py            # PLUGIN_GROUP, discover/load/load_all, build_function_map/build_class_map
│       ├── primitives.py          # PRIMITIVES_MAP lives here (host-only; no plugin references it)
│       ├── registry.py            # registry generation (unchanged body)
│       ├── executor.py            # graph execution (unchanged body)
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
   - `load_all(names)`.
   - `build_function_map(include=None, exclude=None)` / `build_class_map(...)`: same signatures as before, now
     re-backed by `discover`/`load`. `include=None` → `sorted(discover())`; names are merged in selection order
     (later wins on key collision, e.g. the `print_result` shared by math + string). An unknown name → `LookupError`.
   - Re-exports `PRIMITIVES_MAP` (defined in `coral_app/primitives.py`).

   `registry.py` and `executor.py` **do not import each other**; both import `PRIMITIVES_MAP`,
   `build_function_map`, `build_class_map` from `coral_app`.

   - **`registry.py`**: `generate_registry()` (introspects function/class maps + primitive names),
     `python_type_to_string()`, `save_registry_to_file(filename, modules=...)`.
   - **`executor.py`**: `WorkflowExecutor(workflow_file, modules=...)` — see [Data flow](#data-flow).

4. **`coral-app/cli.py`** — Coral-compatible CLI entry point (argparse):
   - Global `-p/--plugin` names the plugins to load (comma-separated; empty = all installed).
   - `register` subcommand → `save_registry_to_file()` (writes `node_types.json` into the cwd).
   - `run` subcommand → `WorkflowExecutor(...).execute()`.
   - Empty `-p` resolves to `discover()` (all installed), passed explicitly.
   - Exposed as the `coral` console script; wrapped by `coral-py` for the platform.

### Workflow JSON Structure

**Network Files** (e.g., `network-from-fe.json`):
Located at: `workflow.nodes` and `workflow.edges`

Nodes are **lean**: each carries only its `type` (plus `value` for primitives); the executor infers
the kind from `type`, so `node_type`/`method_name` are not part of the graph.
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
discover() (no import) ─→ load(requested names) ─→ plugin.get_functions()/get_classes()
   ─→ host merges → function_map / class_map ─→ registry.py (register) | executor.py (run)
```

1. **Discover/Load**: the host lists installed plugins (no import) and loads only the requested names.
2. **Build maps**: each loaded plugin's `get_functions()`/`get_classes()` are merged into `function_map` /
   `class_map` (selection order; later wins). Primitives come from the host `PRIMITIVES_MAP`.
3. **Load graph**: workflow loaded from JSON (`workflow.nodes` and `workflow.edges`).
4. **Sort**: topological sort determines execution order (detects cycles using Kahn's algorithm).
5. **Execute**: nodes executed in dependency order:
   - **Primitive nodes**: Return typed value (type conversion via `PRIMITIVES_MAP`)
   - **Function nodes**: Collect inputs from edges (sorted by `target_input`), call function
   - **Constructor nodes**: Collect inputs, instantiate class from `class_map`
   - **Method nodes**: First input is instance, remaining inputs are parameters
6. **Store**: Results stored in `executor.results` dictionary for downstream nodes.

### Node Execution Model

Each node's kind is inferred from its `type` by `WorkflowExecutor._classify()` (membership in
`PRIMITIVES_MAP` / `function_map` / `class_map`, plus the `Class.method` split), then executed:

**Primitive nodes** (`type` in `PRIMITIVES_MAP`):
- Extract `value` and `type` from node definition
- Convert value using `PRIMITIVES_MAP[type]` (handles string-to-type conversion from JSON)
- Store result directly

**Function nodes** (`type` in `function_map`):
- Look up function in `function_map` using `type`
- Collect inputs from incoming edges sorted by `target_input` index
- Map inputs to function parameters positionally using `inspect.signature()`
- Execute function with kwargs, store result

**Constructor nodes** (`type` in `class_map`):
- Look up class in `class_map` using `type` field
- Collect constructor inputs from edges (sorted by `target_input`)
- Map inputs to `__init__` parameters (excluding `self`)
- Instantiate class, store instance

**Method nodes** (`type` is `Class.method` with the class in `class_map`):
- Parse the fully qualified `type` (format: `"ClassName.method_name"`)
- First input (lowest `target_input`) must be instance of `ClassName`
- Remaining inputs are method parameters
- Use `getattr(instance, method_name)` to get bound method
- Execute method with parameters, store result

### PhiFlow Integration

The `phi_flow/` directory contains physics simulation examples using the PhiFlow library:
- Fluid dynamics simulations (smoke plumes, obstacles)
- Uses JIT compilation for performance
- Supports multiple backends (JAX, PyTorch, TensorFlow)
- Wrapper classes in `packages/coral-plugin-phiflow/src/coral_plugin_phiflow/__init__.py` provide a simplified
  API for workflow integration.

## Key Constraints and Design Decisions

- **Edge ordering is critical**: Function/method parameter order determined by `target_input` values on edges (sorted ascending)
- **Type system**: Maps Python types (int, float, str, bool, None, Any) to string representations via `PRIMITIVES_MAP`
- **No cycles**: Workflow graphs must be acyclic (DAG) - executor will raise `ValueError` if cycle detected
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
- **C extension limitation**: C extension classes (like `datetime`) only register constructors, not methods (due to `inspect.isfunction()` behavior)

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
  returning False for C extension methods). For full method support, create a pure-Python wrapper class.

### Type Hint Requirements

The registry system requires explicit type hints:
- Use basic Python types: `int`, `float`, `str`, `bool`
- Use `Any` from `typing` for flexible types (note: has issues with `function-schema` library)
- Return type `None` indicates no output
- Missing type hints default to `"any"` in registry
- Do **not** use `from __future__ import annotations` (see Key Constraints above)
