# coral-python
Coral for python libraries

The **wheel** is the line between the two audiences: developers work in the uv workspace and *build*
wheels; end users *install* those wheels with `pip` and never touch uv.

- [Development setup](#development-setup) — developers: `uv` only, ending in the wheels.
- [Installation](#installation) — end users: `pip` only, starting from the wheels.

## Development setup

For working *on* coral-python. This is a
[uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/): a monorepo of independently
installable packages — the framework at the root (`coral-core/`, `coral-app/`) and one directory per
plugin under `plugins/` — wired together for development by the virtual root `pyproject.toml` and
pinned in `uv.lock`.

### Prerequisites
- Python 3.12+
- [uv](https://github.com/astral-sh/uv) installed (uv manages the interpreter and the environment —
  do not use `pip` here)
- `ffmpeg` installed and on `PATH` (e.g. `apt install ffmpeg` / `brew install ffmpeg`) — only if you
  work with the `phiflow` plugin: required for `.mp4` export from the PhiFlow scripts and the
  `phiflow_plot_and_save` workflow node, which call matplotlib's `anim.save(..., writer='ffmpeg')`.
  Not needed for `.gif` export.

```bash
# Create .venv and install the whole workspace (incl. the dev group) from the lockfile
uv sync
```

That installs every workspace package **editable**, plugins included — so entry-point discovery finds
each `coral-plugin-*` straight from the checkout and `coral -p "math" run …` works immediately. A
developer never runs `pip` and never installs a plugin separately.

Then either activate the environment (`source .venv/bin/activate`) or prefix commands with `uv run`
(e.g. `uv run coral --help`). `uv run` auto-syncs the environment against `uv.lock` before running.

Finally, install the git hook — once per clone:

```bash
uv run pre-commit install
```

Every commit then runs `ruff format` and `ruff check` on the staged Python files. A formatting
failure rewrites the files: `git add -u` and commit again. Tests are not in the hook (no runners
yet) — run `uv run pytest` yourself.

### Managing Dependencies

```bash
# Add a runtime dependency to a specific workspace package (updates its pyproject.toml + uv.lock)
uv add --package coral-plugin-phiflow <package-name>

# Add a dev-only dependency (to the workspace root dev group)
uv add --dev <package-name>

# Re-resolve / update the lockfile and sync the environment
uv lock
uv sync
```

> Each package declares its own dependencies in its own `pyproject.toml`
> (e.g. `coral-plugin-phiflow` owns `phiflow`/`jax`/`h5py`); the per-package `pyproject.toml` files +
> `uv.lock` are the source of truth for dependencies.

### Building the wheels (for end users)

This is the hand-off point: one command produces a wheel per package into `dist/`. Ship that
directory (or its contents) to end users, who install it with `pip` as described in
[Installation](#installation) below. Building is only for distribution — it is not part of the
development loop, and you do not install the wheels to test your own changes.

```bash
uv build --all-packages --wheel --out-dir dist
```

## Installation

For running `coral`, not developing it. You need a set of `coral-*` wheels — either a `dist/`
directory handed to you, or one built as above. No `uv` required.

### Prerequisites
- Python 3.12+ with `pip`
- `ffmpeg` on `PATH`, as above, only if you use the `phiflow` plugin

### Install with pip

The host works on its own; plugins are optional and additive.

```bash
# 1. (Recommended) create and activate a virtual environment
python3.12 -m venv .venv
source .venv/bin/activate

# 2. Install the host. `--find-links dist` lets pip resolve the internal coral-core dependency
#    from the local wheels (it is not published on PyPI).
pip install --find-links dist coral-app

# 3. Optionally add plugins — each is discovered automatically and adds its own nodes:
pip install --find-links dist coral-plugin-math
pip install --find-links dist coral-plugin-string
pip install --find-links dist coral-plugin-phiflow   # also pulls phiflow/jax/h5py from PyPI (heavy)
```

`coral-app` alone gives a working `coral` CLI with the built-in primitives; every `coral-plugin-*`
you add is picked up via entry-point discovery. Verify with `coral --help` or `coral register`
(writes `node_types.json`). Then head to [Usage](#usage) — run `coral` directly.

## Usage

`coral` is a **coral-compatible CLI** (the `coral-app` console script): a global `-p/--plugin` option naming the
plugins to load (comma-separated, e.g. `"math,string"`; empty = all installed) plus two subcommands — `register`
(emit the node registry) and `run` (execute a workflow). `-p/--plugin` must precede the subcommand. This mirrors
the C++ `coral` binary so the DealiiX platform can drive this backend via the
[`coral-py` launcher](#coral-launcher-for-the-dealiix-platform).

> Run the commands below inside the activated environment. From a pip install, `coral` is on `PATH`
> once the venv is activated; from the uv workspace, activate `.venv` or prefix each command with
> `uv run` (e.g. `uv run coral run`).

### 1. Running the Workflow Executer

Use the `run` subcommand with the path to a workflow graph:
```bash
coral run path/to/your/workflow.json
```

An example phiflow workflow ships with the plugin that gives it meaning, under
`plugins/coral-phiflow/examples/phiflow/`:
```bash
coral -p "phiflow" run plugins/coral-phiflow/examples/phiflow/network-from-fe.json
```

Load specific plugins with `-p/--plugin` (before the subcommand):
```bash
# Load only math operations
coral -p "math" run workflow.json

# Load multiple plugins
coral -p "math,string,phiflow" run workflow.json
```

**Default behavior**: When `-p/--plugin` is omitted, all installed plugins are loaded (via entry-point
discovery). Primitives are always included. An unknown `-p` name fails loud with `LookupError`.

**Available plugins** (each an installed `coral-plugin-*` package):
- `phiflow` - PhiFlow physics simulation wrappers
- `math` - Mathematical operations (`add`, `multiply`, `math.sqrt`, etc.) and `Calculator` class
- `string` - String processing utilities (`StringProcessor` class)

### 2. Generating the Workflow Registry File

Use the `register` subcommand. It writes `node_types.json` into the current directory (the filename the
DealiiX platform probes for):
```bash
coral register
```

Generate the registry for specific plugins:
```bash
# Math operations only
coral -p "math" register

# Multiple plugins
coral -p "math,string,phiflow" register
```

**Custom output filename:**
```bash
coral register --output="custom_registry.json"
```

### 3. Getting help
```bash
coral --help
```

### Coral launcher (for the DealiiX platform)

`coral-py` runs the `coral` console script inside this repo's uv workspace while preserving the caller's working
directory, so `register` writes `node_types.json` into that directory. It therefore needs the
[development setup](#development-setup) (a uv checkout), not a pip install — from a pip install the platform can
point `coralBinaryPath` straight at the `coral` executable. Point the platform's `coralBinaryPath` at it and set
`coralPluginPath` to the plugin list:
```bash
./coral-py -p "math" register            # writes node_types.json into the current directory
./coral-py -p "math" run workflow.json
```

### More info about the plugin packages
Each plugin is a self-contained distribution under `plugins/coral-*/`. See
[`docs/ONBOARDING.md`](docs/ONBOARDING.md) for how discovery works and how to add a new plugin.

## Extending coral-python

Extending or modifying coral-python? Start with [`docs/ONBOARDING.md`](docs/ONBOARDING.md) — the onboarding
guide covering goals, architecture, the two contracts with the DealiiX platform, how to add a library or
change internals, design rationale, and an honest account of strengths and weaknesses. (This `README.md`
is setup + commands; `CLAUDE.md` is the AI-assisted-development mechanics reference.)

## Testing

> Developer-only, and run from the workspace root: activate `.venv` first, or prefix each command
> with `uv run` (e.g. `uv run pytest`). See [Development setup](#development-setup).

Run All Tests:
```bash
pytest                 # every package's suite plus the repo-level tests
pytest -m "not slow"   # the fast lane (~0.8s): everything but one simulation and the wheel build
pytest -m slow         # the PhiFlow simulation and the wheel acceptance test
```

Run Tests with Coverage:
```bash
pytest --cov --cov-report=html
open htmlcov/index.html  # View coverage report
```

Select by **path**, not by plugin marker — each test lives in the package it is about:
```bash
pytest coral-app/tests                     # the host, on its designed specimen
pytest plugins/coral-math/tests            # the math plugin
pytest plugins/coral-math/tests/unit       # just its functions and classes
pytest plugins/coral-phiflow/tests/system  # its graphs through the host
pytest tests                                        # only what names no plugin at all
```

Run a Specific Test Class or Function:
```bash
pytest coral-app/tests/test_executor.py::TestPrimitiveNodes
pytest coral-app/tests/test_executor.py::TestFunctionNodes::test_a_zero_input_function_runs
```

A plugin's suite skips itself when that plugin is not installed, so a subset install yields named skips
rather than errors. See [`tests/README.md`](tests/README.md) for the layout and the rule behind it.

Verbose Output:
```bash
pytest -v          # Verbose
pytest -vv         # Extra verbose
pytest -s          # Show print statements
```

### More info about the tests suite
For more info see the [README.md](/tests/README.md) in the `tests` directory.