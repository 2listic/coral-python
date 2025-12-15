import json
import inspect
from typing import Any, Dict, List, get_origin

from functions import FUNCTION_MAP, PRIMITIVES


def generate_registry(function_map: Dict[str, callable], primitives: List[str] = None) -> Dict:
    """Generate a registry JSON from function definitions"""

    if (primitives is None or function_map is None):
        raise ValueError("primitives and function_map must be provided")

    registry = {}
    node_id = 0

    # Add primitive types
    for prim_type in primitives:
        registry[str(node_id)] = {
            "value": None,
            "inputs": [],
            "outputs": [-1],
            "node_type": "primitive",
            "type": prim_type
        }
        node_id += 1

    # Add functions
    for func_name, func in function_map.items():
        # Get function signature
        sig = inspect.signature(func)

        arguments = []
        inputs = []

        # Process input parameters
        param_idx = 0
        for _, param in sig.parameters.items():
            json_type = python_type_to_json_type(param.annotation)

            arguments.append({
                "connection_type": "input",
                "type": json_type
            })
            inputs.append(param_idx)
            param_idx += 1

        # Process return type (output)
        return_annotation = sig.return_annotation
        return_json_type = python_type_to_json_type(return_annotation)

        # Only add output if function returns something (not None)
        if return_annotation is not None and return_annotation != type(None) and return_annotation != inspect.Signature.empty:
            arguments.append({
                "connection_type": "output",
                "type": return_json_type
            })
            outputs = [param_idx]
        else:
            outputs = []

        registry[str(node_id)] = {
            "arguments": arguments,
            "inputs": inputs,
            "outputs": outputs,
            "node_type": "function",
            "method_name": func_name
        }
        node_id += 1

    return registry


def python_type_to_json_type(py_type) -> str:
    """Convert Python type annotation to JSON schema type string"""

    # Handle empty/missing annotations
    if py_type is inspect.Signature.empty or py_type is None:
        return "any"

    # Handle typing module types (like Any)
    if py_type is Any:
        return "any"

    # Handle basic types
    type_map = {
        int: "int",
        float: "float",
        str: "string",
        bool: "bool",
        type(None): "none"
    }

    if py_type in type_map:
        return type_map[py_type]

    # Handle typing generics (Optional, Union, etc.)
    origin = get_origin(py_type)
    if origin is not None:
        # For Optional, Union, etc., just return "any" for simplicity
        # You could make this more sophisticated
        return "any"

    # Default to "any" for unknown types
    return "any"


def save_registry_to_file(filename: str = "registry-py-mwe.json"):
    """Generate and save the registry to a JSON file"""
    registry = generate_registry(FUNCTION_MAP, PRIMITIVES)

    with open(filename, 'w') as f:
        json.dump(registry, f, indent=2)

    print(f"Registry saved to {filename}")
    return registry
