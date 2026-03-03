# Definitions Package

This package provides modular function and class definitions for the Coral workflow system.

## Architecture

The definitions are organized into domain-specific modules:

- **math_ops.py**: Mathematical operations (`add`, `multiply`, `math.sqrt`, etc.) and the `Calculator` class
- **string_ops.py**: String processing utilities (`StringProcessor` class)
- **phiflow_defs.py**: PhiFlow physics simulation wrappers
- **primitives.py**: Type mapping for primitive values

## Basic Usage

By default, all available modules are loaded:

```python
from definitions import FUNCTION_MAP, CLASS_MAP, PRIMITIVES_MAP

# These contain all available definitions
print(len(FUNCTION_MAP))  # All registered functions
print(len(CLASS_MAP))     # All registered classes
```

## Selective Module Loading

You can customize which modules to load using the builder functions:

```python
from definitions import build_function_map, build_class_map

# Load only PhiFlow definitions for physics simulations
FUNCTION_MAP = build_function_map(include=['phiflow'])
CLASS_MAP = build_class_map(include=['phiflow'])

# Load everything except PhiFlow
FUNCTION_MAP = build_function_map(exclude=['phiflow'])
CLASS_MAP = build_class_map(exclude=['phiflow'])

# Load only math and string operations
FUNCTION_MAP = build_function_map(include=['math', 'string'])
CLASS_MAP = build_class_map(include=['math', 'string'])
```

## Available Module Names

- `'math'` - Mathematical operations and Calculator class
- `'string'` - String processing utilities
- `'phiflow'` - PhiFlow physics simulation wrappers

## Adding New Modules

To add a new domain-specific module:

1. Create a new file in `definitions/` (e.g., `mymodule.py`)
2. Implement `get_functions()` and `get_classes()` that return dictionaries
3. Import the module in `definitions/__init__.py`
4. Add it to the `modules` dictionary in both `build_function_map()` and `build_class_map()`

### Example Module Template

```python
# definitions/mymodule.py
from typing import Any, Dict

def my_function(x: float) -> float:
    """My custom function"""
    return x * 2

class MyClass:
    """My custom class"""
    def __init__(self, value: float):
        self.value = value

    def double(self) -> float:
        return self.value * 2

def get_functions() -> Dict[str, Any]:
    """Return function definitions"""
    return {
        "my_function": my_function,
    }

def get_classes() -> Dict[str, Any]:
    """Return class definitions"""
    return {
        "MyClass": MyClass,
    }
```

Then update `definitions/__init__.py`:

```python
from . import math_ops, string_ops, phiflow_defs, primitives, mymodule

def build_function_map(include=None, exclude=None):
    modules = {
        'math': math_ops,
        'string': string_ops,
        'phiflow': phiflow_defs,
        'mymodule': mymodule,  # Add here
    }
    # ... rest of implementation
```

## Benefits

- **Library Independence**: Each module handles its own import failures gracefully
- **Selective Registration**: Load only the definitions needed for your application
- **Easier Maintenance**: Domain-specific code stays together
- **Reusability**: Definition sets can be shared across projects
- **Clear Dependencies**: Import errors are isolated to specific modules
