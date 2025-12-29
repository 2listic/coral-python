# coral-python
Coral for python libraries

## Installation

### Prerequisites
- Python 3.6+
- [uv](https://github.com/astral-sh/uv) installed 

## Setup

```bash
# Create virtual environment
uv venv

# Activate virtual environment
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate  # Windows

# Install dependencies without extras
uv pip sync requirements.txt
```

### Managing Dependencies

#### Install new packages with [uv pip compile](https://docs.astral.sh/uv/pip/compile/)

```bash
# Add the package to requirements.in

echo "jax" >> requirements.in

#Recompile requirements.txt
uv pip compile requirements.in -o requirements.txt

# Sync your environment
uv pip sync requirements.txt
```

## Usage

### Running a stand-alone Phi-flow simulation

```bash
# Run a simulation and then check the mp4 or gif file produced
python one_obstacle.py3
```

### Running the Workflow Executer

**Run with default workflow file (network-from-fe.json):**
```bash
python main.py
```

**Run with a specific workflow file:**
```bash
python main.py path/to/your/workflow.json
```

**Run with specific modules loaded:**
```bash
# Load only math operations
python main.py workflow.json --modules="math"

# Load multiple modules
python main.py workflow.json --modules="math,string,phiflow"
```

**Default behavior**: When no `--modules` flag is provided, only the `phiflow` module is loaded (optimal for physics simulations). Primitives are always included.

**Available modules**:
- `phiflow` - PhiFlow physics simulation wrappers (default)
- `math` - Mathematical operations (`add`, `multiply`, `math.sqrt`, etc.) and `Calculator` class
- `string` - String processing utilities (`StringProcessor` class)

### Generating the Workflow Registry File

**Generate the default registry file registry-py-mwe.json:**
```bash
python main.py --generate-registry
```

**Generate registry with specific modules:**
```bash
# Generate registry for math operations only
python main.py --generate-registry --modules="math"

# Generate registry for all modules
python main.py --generate-registry --modules="math,string,phiflow"
```

**Generate custom output path for registry file:**
```bash
python main.py --generate-registry --registry-output="custom_registry.json" --modules="math"
```

**Get help:**
```bash
python main.py --help
```