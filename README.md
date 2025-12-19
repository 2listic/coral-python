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

**Run with default workflow file (network-py-mwe.json):**
```bash
python main.py
```

**Run with a specific workflow file:**
```bash
python main.py path/to/your/workflow.json
```

### Generating the Workflow Registry File

**Generate the default registry file registry-py-mwe.json:**
```bash
python main.py --generate-registry
```

**Generate custom output path for registry file:**
```bash
python main.py --generate-registry --registry-output custom_registry.json
```

**Get help:**
```bash
python main.py --help
```