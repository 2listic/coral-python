# coral-python
Coral for python libraries

## Installation

### Prerequisites
- Python 3.12+
- [uv](https://github.com/astral-sh/uv) installed
- `ffmpeg` installed and on `PATH` (e.g. `apt install ffmpeg` / `brew install ffmpeg`) — required for `.mp4`
  export from the PhiFlow scripts and the `phiflow_plot_and_save` workflow node, which call matplotlib's
  `anim.save(..., writer='ffmpeg')`. Not needed for `.gif` export.

## Setup

This is a [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/): a monorepo of
independently installable packages under `packages/*` (`coral-core`, `coral-app`, and one
`coral-plugin-*` per plugin), wired together for development by the virtual root `pyproject.toml`
and pinned in `uv.lock`.

```bash
# Create .venv and install every workspace package editable (incl. the dev group) from the lockfile
uv sync
```

Then either activate the environment (`source .venv/bin/activate`) or prefix commands with `uv run`
(e.g. `uv run coral --help`). `uv run` auto-syncs the environment against `uv.lock` before running.

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

> Each package declares its own dependencies in its `packages/<name>/pyproject.toml`
> (e.g. `coral-plugin-phiflow` owns `phiflow`/`jax`/`h5py`). `requirements.in` / `requirements.txt`
> are retained for reference only; the per-package `pyproject.toml` files + `uv.lock` are the source
> of truth for dependencies.

## Usage

`coral` is a **coral-compatible CLI** (the `coral-app` console script): a global `-p/--plugin` option naming the
plugins to load (comma-separated, e.g. `"math,string"`; empty = all installed) plus two subcommands — `register`
(emit the node registry) and `run` (execute a workflow). `-p/--plugin` must precede the subcommand. This mirrors
the C++ `coral` binary so the DealiiX platform can drive this backend via the
[`coral-py` launcher](#coral-launcher-for-the-dealiix-platform).

> Run the commands below inside an activated venv, or prefix each with `uv run` (e.g. `uv run coral run`).

### 1. Running a stand-alone Phi-flow simulation

```bash
# Run a simulation and then check the mp4 or gif file produced
python phi_flow/one_obstacle.py
```

### 2. Running the Workflow Executer

Use the `run` subcommand. With no graph argument it defaults to `network-from-fe.json`:
```bash
coral run
```

Run a specific workflow file:
```bash
coral run path/to/your/workflow.json
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

### 3. Generating the Workflow Registry File

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

### Coral launcher (for the DealiiX platform)

`coral-py` runs the `coral` console script inside this repo's uv workspace while preserving the caller's working
directory, so `register` writes `node_types.json` into that directory. Point the platform's `coralBinaryPath` at
it and set `coralPluginPath` to the plugin list:
```bash
./coral-py -p "math" register            # writes node_types.json into the current directory
./coral-py -p "math" run workflow.json
```

### More info about the plugin packages
Each plugin is a self-contained distribution under `packages/coral-plugin-*/`. See
[`docs/ONBOARDING.md`](docs/ONBOARDING.md) for how discovery works and how to add a new plugin.

### 4. Getting help
```bash
coral --help
```

## Development

Extending or modifying coral-python? Start with [`docs/ONBOARDING.md`](docs/ONBOARDING.md) — the onboarding
guide covering goals, architecture, the two contracts with the DealiiX platform, how to add a library or
change internals, design rationale, and an honest account of strengths and weaknesses. An Italian version is
at [`docs/ONBOARDING.it.md`](docs/ONBOARDING.it.md). (This `README.md` is setup + commands; `CLAUDE.md` is the
AI-assisted-development mechanics reference.)

## Testing

Run All Tests:
```bash
pytest
```

Run Tests with Coverage:
```bash
pytest --cov=. --cov-report=html
open htmlcov/index.html  # View coverage report
```

Run a Specific Test File:
```bash
pytest tests/test_executor.py
pytest tests/test_integration.py
```

Run a Specific Test Class:
```bash
pytest tests/test_executor.py::TestPrimitiveNodeExecution
pytest tests/test_integration.py::TestPhiFlowWorkflows
```

Run a Specific Test Function:
```bash
pytest tests/test_executor.py::TestPrimitiveNodeExecution::test_int_primitive
```

Running Specific Test Categories:

```bash
pytest -m unit        # To be marked
pytest -m integration # Integration tests with Json network files
pytest -m math        # Math module tests
pytest -m phiflow     # PhiFlow tests (requires PhiFlow)
pytest -m string      # String module tests
```

Verbose Output:
```bash
pytest -v          # Verbose
pytest -vv         # Extra verbose
pytest -s          # Show print statements
```

### More info about the tests suite
For more info see the [README.md](/tests/README.md) in the `tests` directory.