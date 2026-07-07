# coral-python
Coral for python libraries

## Installation

### Prerequisites
- Python 3.12+
- [uv](https://github.com/astral-sh/uv) installed

## Setup

This is a [uv project](https://docs.astral.sh/uv/concepts/projects/): dependencies are declared in
`pyproject.toml` and pinned in `uv.lock`.

```bash
# Create .venv and install all dependencies (incl. the dev group) from the lockfile
uv sync
```

Then either activate the environment (`source .venv/bin/activate`) or prefix commands with `uv run`
(e.g. `uv run python main.py`). `uv run` auto-syncs the environment against `uv.lock` before running.

### Managing Dependencies

```bash
# Add a runtime dependency (updates pyproject.toml + uv.lock, then syncs the env)
uv add <package-name>

# Add a dev-only dependency
uv add --dev <package-name>

# Re-resolve / update the lockfile and sync the environment
uv lock
uv sync
```

> `requirements.in` / `requirements.txt` are retained for reference only; `pyproject.toml` + `uv.lock`
> are now the source of truth for dependencies.

## Usage

`main.py` is a **coral-compatible CLI**: a global `-p/--plugin` option naming the definition modules to load
(comma-separated, e.g. `"math,string"`; empty = all) plus two subcommands — `register` (emit the node registry)
and `run` (execute a workflow). `-p/--plugin` must precede the subcommand. This mirrors the C++ `coral` binary so
the DealiiX platform can drive this backend via the [`coral-py` launcher](#coral-launcher-for-the-dealiix-platform).

> Run the commands below inside an activated venv, or prefix each with `uv run` (e.g. `uv run python main.py run`).

### 1. Running a stand-alone Phi-flow simulation

```bash
# Run a simulation and then check the mp4 or gif file produced
python one_obstacle.py
```

### 2. Running the Workflow Executer

Use the `run` subcommand. With no graph argument it defaults to `network-from-fe.json`:
```bash
python main.py run
```

Run a specific workflow file:
```bash
python main.py run path/to/your/workflow.json
```

Load specific modules with `-p/--plugin` (before the subcommand):
```bash
# Load only math operations
python main.py -p "math" run workflow.json

# Load multiple modules
python main.py -p "math,string,phiflow" run workflow.json
```

**Default behavior**: When `-p/--plugin` is omitted, all available modules are loaded. Primitives are always included.

**Available modules**:
- `phiflow` - PhiFlow physics simulation wrappers (default)
- `math` - Mathematical operations (`add`, `multiply`, `math.sqrt`, etc.) and `Calculator` class
- `string` - String processing utilities (`StringProcessor` class)

### 3. Generating the Workflow Registry File

Use the `register` subcommand. It writes `node_types.json` into the current directory (the filename the
DealiiX platform probes for):
```bash
python main.py register
```

Generate the registry for specific modules:
```bash
# Math operations only
python main.py -p "math" register

# Multiple modules
python main.py -p "math,string,phiflow" register
```

**Custom output filename:**
```bash
python main.py register --output="custom_registry.json"
```

### Coral launcher (for the DealiiX platform)

`coral-py` runs `main.py` inside this repo's uv project while preserving the caller's working directory, so
`register` writes `node_types.json` into that directory. Point the platform's `coralBinaryPath` at it and set
`coralPluginPath` to the module list:
```bash
./coral-py -p "math" register            # writes node_types.json into the current directory
./coral-py -p "math" run workflow.json
```

### More info about the definitions package
See [README.md](definitions/README.md) in the `definitions` directory for more detailed information about how different module definitions are handled.

### 4. Getting help
```bash
python main.py --help
```

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