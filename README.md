# coral-python
Coral for python libraries

## Installation

### Prerequisites
- Python 3.6+
- [uv](https://github.com/astral-sh/uv) installed 

### Setup

```bash
# Create virtual environment
uv venv

# Activate virtual environment
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate  # Windows

# Install dependencies
uv pip install -r requirements.txt

# Run a simulation and then check the mp4 or gif file produced
python one_obstacle.py
```

### Managing Dependencies

**Install a new package:**
```bash
uv pip install <package-name>
echo "<package-name>" >> requirements.in  # Track what YOU installed
uv pip freeze > requirements.txt  # Lock all versions
```

**Update all packages:**
```bash
uv pip install --upgrade -r requirements.txt
uv pip freeze > requirements.txt
```

## Usage

### Running the Workflow Executer

**Run with default workflow file (network-py-mwe.json):**
```bash
python main.py
```

**Run with a specific workflow file:**
```bash
python main.py path/to/your/workflow.json
```

### Generating the Registry File

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