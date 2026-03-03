# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Coral for Python** is a workflow execution system that processes computational graphs defined in JSON format. The system supports four types of nodes:
- **Primitive nodes**: Hold constant values (int, float, string, bool, any)
- **Function nodes**: Execute Python functions with typed inputs and outputs
- **Constructor nodes**: Instantiate Python classes
- **Method nodes**: Call instance methods on objects created by constructor nodes

The project uses PhiFlow for physics simulations and numerical computing.

## Development Commands

### Environment Setup
```bash
# Create and activate virtual environment
uv venv
source .venv/bin/activate  # Linux/Mac

# Install dependencies using uv pip sync (recommended)
uv pip sync requirements.txt

# Or install directly
uv pip install -r requirements.txt
```

### Package Management
```bash
# Add a new package (recommended workflow)
echo "<package-name>" >> requirements.in
uv pip compile requirements.in -o requirements.txt
uv pip sync requirements.txt

# Alternative: direct install (must still update requirements.txt)
uv pip install <package-name>
uv pip freeze > requirements.txt
```

### Running Workflows
```bash
# Execute default workflow (network-from-fe.json) with default modules
python main.py

# Execute specific workflow file
python main.py path/to/workflow.json

# Execute with specific modules loaded
python main.py path/to/workflow.json --modules="math"
python main.py path/to/workflow.json --modules="math,string,phiflow"

# Generate registry from selected modules
python main.py --generate-registry
python main.py --generate-registry --modules="math"
python main.py --generate-registry --modules="math,string,phiflow"

# Generate registry to custom file
python main.py --generate-registry --registry-output="custom-registry.json" --modules="math"
```

**Default module behavior**: When no `--modules` flag is provided, only the `phiflow` module is loaded (optimal for physics simulations). Primitives are always included.

**Available modules**:
- `math` - Mathematical operations and Calculator class
- `string` - StringProcessor class
- `phiflow` - PhiFlow physics simulation wrappers (default)

### Running Standalone PhiFlow Simulations
```bash
# Run a PhiFlow simulation directly (not through workflow system)
python phi_flow/one_obstacle_absorb.py
python phi_flow/multiple_obstacles.py
# Check the generated .mp4 or .gif output file in phi_flow/ directory
```

### Running Tests
```bash
# Run all tests
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
pytest -m math         # Math module tests
pytest -m phiflow      # PhiFlow tests
pytest -m string       # String module tests

# Verbose output with print statements
pytest -v   # Verbose
pytest -vv  # Extra verbose
pytest -s   # Show print statements
```

## Architecture

### Core Components

The system is organized into four main modules:

1. **definitions/** - Modular package for callable functions and classes:
   - **`definitions/__init__.py`**: Exports `build_function_map()`, `build_class_map()`, and `PRIMITIVES_MAP`
   - **`definitions/primitives.py`**: Maps type strings to Python types (int, float, str, bool, any, none)
   - **`definitions/math_ops.py`**: Mathematical operations (`add`, `multiply`, `math.sqrt`, etc.) and `Calculator` class
   - **`definitions/string_ops.py`**: `StringProcessor` class and `print_result` function
   - **`definitions/phiflow_defs.py`**: PhiFlow physics simulation wrappers (if available)

   **Module loading**: Use `--modules` flag to control which definitions are loaded. Default: `phiflow` only.

2. **registry.py** - Registry generation and type conversion:
   - `generate_registry()`: Introspects functions and classes to create JSON schema
   - `python_type_to_string()`: Converts Python type hints to string representations
   - `save_registry_to_file()`: Saves registry to JSON file, accepts `modules` parameter
   - Generates entries for primitives, functions, constructors, and methods

3. **executor.py** - Workflow execution engine:
   - **`WorkflowExecutor`**: Executes workflow JSON files by:
     - Loading specified modules via `modules` parameter (defaults to `['phiflow']`)
     - Building function and class maps dynamically based on loaded modules
     - Performing topological sort (Kahn's algorithm) to determine execution order
     - Evaluating primitive nodes (returning their typed `value`)
     - Executing function nodes with inputs from connected edges
     - Instantiating classes via constructor nodes
     - Calling instance methods via method nodes
     - Storing results for downstream nodes

4. **main.py** - CLI entry point with argparse interface:
   - Accepts `--modules` flag to control which definition modules are loaded
   - Passes module list to both `WorkflowExecutor` and `save_registry_to_file()`

### Workflow JSON Structure

**Network Files** (e.g., `network-from-fe.json`):
Located at: `workflow.nodes` and `workflow.edges`

Node types:
- Primitive: `{"value": <val>, "node_type": "primitive", "type": "<type>"}`
- Function: `{"node_type": "function", "method_name": "<func_name>"}`
- Constructor: `{"node_type": "constructor", "type": "<ClassName>"}`
- Method: `{"node_type": "method", "method_name": "<ClassName>.<method_name>"}`

Edge format:
- `{"source": "<source_id>", "target": "<target_id>", "source_output": <idx>, "target_input": <idx>}`
- **CRITICAL**: `target_input` determines parameter ordering for function/method calls

**Registry Files** (e.g., `registry-py.json`):
- Auto-generated schema describing all available node types
- Each entry has:
  - `arguments`: Array with `connection_type` ("input"/"output") and `type`
  - `inputs`: List of input indices
  - `outputs`: List of output indices (or `[-1]` for constructors/primitives)
  - `node_type`: "primitive", "function", "constructor", or "method"

### Data Flow

1. **Load**: Workflow loaded from JSON (`workflow.nodes` and `workflow.edges`)
2. **Sort**: Topological sort determines execution order (detects cycles using Kahn's algorithm)
3. **Execute**: Nodes executed in dependency order:
   - **Primitive nodes**: Return typed value (type conversion via `PRIMITIVES_MAP`)
   - **Function nodes**: Collect inputs from edges (sorted by `target_input`), call function
   - **Constructor nodes**: Collect inputs, instantiate class from `CLASS_MAP`
   - **Method nodes**: First input is instance, remaining inputs are parameters
4. **Store**: Results stored in `executor.results` dictionary for downstream nodes

### Node Execution Model

Each node type follows a specific execution pattern in [executor.py](executor.py):

**Primitive nodes** (`node_type: "primitive"`):
- Extract `value` and `type` from node definition
- Convert value using `PRIMITIVES_MAP[type]` (handles string-to-type conversion from JSON)
- Store result directly

**Function nodes** (`node_type: "function"`):
- Look up function in `FUNCTION_MAP` using `method_name`
- Collect inputs from incoming edges sorted by `target_input` index
- Map inputs to function parameters positionally using `inspect.signature()`
- Execute function with kwargs, store result

**Constructor nodes** (`node_type: "constructor"`):
- Look up class in `CLASS_MAP` using `type` field
- Collect constructor inputs from edges (sorted by `target_input`)
- Map inputs to `__init__` parameters (excluding `self`)
- Instantiate class, store instance

**Method nodes** (`node_type: "method"`):
- Parse fully qualified `method_name` (format: `"ClassName.method_name"`)
- First input (lowest `target_input`) must be instance of `ClassName`
- Remaining inputs are method parameters
- Use `getattr(instance, method_name)` to get bound method
- Execute method with parameters, store result

### PhiFlow Integration

The `phi_flow/` directory contains physics simulation examples using the PhiFlow library:
- Fluid dynamics simulations (smoke plumes, obstacles)
- Uses JIT compilation for performance
- Supports multiple backends (JAX, PyTorch, TensorFlow)
- Wrapper classes in [definitions/phiflow_defs.py](definitions/phiflow_defs.py) provide simplified API for workflow integration

## Key Constraints and Design Decisions

- **Edge ordering is critical**: Function/method parameter order determined by `target_input` values on edges (sorted ascending)
- **Type system**: Maps Python types (int, float, str, bool, None, Any) to string representations via `PRIMITIVES_MAP`
- **No cycles**: Workflow graphs must be acyclic (DAG) - executor will raise `ValueError` if cycle detected
- **Naming conventions**:
  - Functions: Use simple names in `FUNCTION_MAP` (e.g., `"add"`, `"math.sqrt"`)
  - Methods: Use fully qualified names (e.g., `"Calculator.add_to_value"`)
  - Classes: Class name becomes the `type` field for constructors (e.g., `"Calculator"`)
- **Type hint requirement**: All functions/methods must have type hints for proper registry generation
- **C extension limitation**: C extension classes (like `datetime`) only register constructors, not methods (due to `inspect.isfunction()` behavior)

## Adding New Definitions

The definitions system is modular. Add new functions and classes to the appropriate module file in `definitions/`.

### Adding Custom Functions

To add a new function to the workflow system:

1. **Choose or create a module file** in `definitions/`:
   - For math operations: Add to `definitions/math_ops.py`
   - For string operations: Add to `definitions/string_ops.py`
   - For PhiFlow wrappers: Add to `definitions/phiflow_defs.py`
   - For new domains: Create a new file (e.g., `definitions/numpy_ops.py`)

2. **Define the function with type hints**:
```python
# In definitions/math_ops.py
def my_function(param1: float, param2: str) -> int:
    """Function description"""
    result = ...
    print(f"my_function({param1}, {param2}) = {result}")
    return result
```

3. **Add to the module's `get_functions()`**:
```python
def get_functions() -> Dict[str, Any]:
    """Return math function definitions"""
    return {
        "add": add,
        "multiply": multiply,
        "my_function": my_function,  # Add here
        # ...
    }
```

4. **Regenerate registry with the appropriate module**:
```bash
python main.py --generate-registry --modules="math"
```

5. The function is now available when the module is loaded

### Registering External Library Functions

External library functions can be registered by creating wrapper functions with proper type hints.

**Example - Adding a NumPy function:**

```python
# Create definitions/numpy_ops.py
import numpy as np
from typing import Any, Dict

def numpy_mean(values: list) -> float:
    """Calculate mean using NumPy"""
    result = np.mean(values)
    print(f"numpy.mean({values}) = {result}")
    return float(result)

def get_functions() -> Dict[str, Any]:
    return {
        "numpy.mean": numpy_mean,
    }

def get_classes() -> Dict[str, Any]:
    return {}
```

Then register the module in `definitions/__init__.py`:
```python
from . import math_ops, string_ops, phiflow_defs, primitives, numpy_ops

def build_function_map(include=None, exclude=None):
    modules = {
        'math': math_ops,
        'string': string_ops,
        'phiflow': phiflow_defs,
        'numpy': numpy_ops,  # Add here
    }
    # ... rest of implementation
```

**Why wrappers are needed:**
- Standard library functions often lack type hints
- Registry generation requires type annotations for proper schema creation
- Wrappers provide control over logging and error handling
- Type conversion may be needed (e.g., NumPy types to Python types)

### Registering Classes

Classes can be registered in any module's `get_classes()` function:

```python
# In definitions/math_ops.py
class Calculator:
    """A simple calculator class"""
    def __init__(self, initial_value: float = 0.0):
        self.value = initial_value

    def add_to_value(self, amount: float) -> float:
        self.value += amount
        print(f"Calculator.add_to_value({amount}) = {self.value}")
        return self.value

def get_classes() -> Dict[str, Any]:
    return {
        "Calculator": Calculator,
    }
```

After updating the module, regenerate the registry:
```bash
python main.py --generate-registry --modules="math"
```

**How it works:**
1. Constructor nodes are generated from `__init__` signatures
2. Method nodes are auto-generated for all public instance methods (non-underscore)
3. Methods use fully qualified names: `ClassName.method_name`
4. First input to method nodes is always the instance

**Limitations:**
- C extension classes (like `datetime`) only register constructors, not methods
- This is due to `inspect.isfunction()` returning False for C extension methods
- For full method support, create Python wrapper classes

### Type Hint Requirements

The registry system requires explicit type hints:
- Use basic Python types: `int`, `float`, `str`, `bool`
- Use `Any` from `typing` for flexible types (note: has issues with `function-schema` library)
- Return type `None` indicates no output
- Missing type hints default to `"any"` in registry
