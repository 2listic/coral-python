import json
import inspect
from typing import Any, Dict, List, get_origin, get_args

from definitions import FUNCTION_MAP, PRIMITIVES_MAP, CLASS_MAP


def generate_registry(
    function_map: Dict[str, callable], primitives: List[str] = None, class_map: Dict[str, type] = None
) -> Dict:
    """Generate a registry JSON from definitions"""

    if primitives is None or function_map is None:
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
            "type": prim_type,
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
            type_string = python_type_to_string(param.annotation)

            arguments.append({
                "connection_type": "input",
                "type": type_string
            })
            inputs.append(param_idx)
            param_idx += 1

        # Process return type (output)
        return_annotation = sig.return_annotation

        # Check if return type is a Tuple - if so, create multiple outputs
        origin = get_origin(return_annotation)
        if origin is tuple:
            # Handle Tuple[Type1, Type2, ...] - create separate output for each element
            tuple_args = get_args(return_annotation)
            outputs = []
            for i, tuple_type in enumerate(tuple_args):
                type_string = python_type_to_string(tuple_type)
                arguments.append({
                    "connection_type": "output",
                    "type": type_string
                })
                outputs.append(param_idx)
                param_idx += 1
        # Only add single output if function returns something (not None)
        elif (
            return_annotation is not None
            and return_annotation != type(None)
            and return_annotation != inspect.Signature.empty
        ):
            return_json_type = python_type_to_string(return_annotation)
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
            "method_name": func_name,
        }
        node_id += 1

    # Add class constructors
    if class_map:
        for class_name, cls in class_map.items():
            # Get __init__ signature
            init_sig = inspect.signature(cls.__init__)

            arguments = []
            inputs = []
            param_idx = 0

            # Process constructor parameters (skip 'self')
            for param_name, param in init_sig.parameters.items():
                if param_name == 'self':
                    continue

                type_string = python_type_to_string(param.annotation)
                arguments.append({
                    "connection_type": "input",
                    "type": type_string
                })
                inputs.append(param_idx)
                param_idx += 1

            # Constructor returns instance (like primitives: outputs = [-1])
            outputs = [-1]

            registry[str(node_id)] = {
                "arguments": arguments,
                "inputs": inputs,
                "outputs": outputs,
                "node_type": "constructor",
                "type": class_name
            }
            node_id += 1

    # Add class methods
    if class_map:
        for class_name, cls in class_map.items():
            # Get all instance methods (exclude __init__, __dunder__, private _methods)
            for method_name in dir(cls):
                if method_name.startswith('_'):
                    continue

                method = getattr(cls, method_name)
                if not callable(method) or not inspect.isfunction(method):
                    continue

                # Get method signature
                sig = inspect.signature(method)

                arguments = []
                inputs = []
                param_idx = 0

                # First input: the instance itself
                arguments.append({
                    "connection_type": "input",
                    "type": class_name
                })
                inputs.append(param_idx)
                param_idx += 1

                # Process method parameters (skip 'self')
                for param_name, param in sig.parameters.items():
                    if param_name == 'self':
                        continue

                    type_string = python_type_to_string(param.annotation)
                    arguments.append({
                        "connection_type": "input",
                        "type": type_string
                    })
                    inputs.append(param_idx)
                    param_idx += 1

                # Process return type
                return_annotation = sig.return_annotation

                # Check if return type is a Tuple - if so, create multiple outputs
                origin = get_origin(return_annotation)
                if origin is tuple:
                    # Handle Tuple[Type1, Type2, ...] - create separate output for each element
                    tuple_args = get_args(return_annotation)
                    outputs = []
                    for i, tuple_type in enumerate(tuple_args):
                        type_string = python_type_to_string(tuple_type)
                        arguments.append({
                            "connection_type": "output",
                            "type": type_string
                        })
                        outputs.append(param_idx)
                        param_idx += 1
                # Only add single output if method returns something (not None)
                elif (
                    return_annotation is not None
                    and return_annotation != type(None)
                    and return_annotation != inspect.Signature.empty
                ):
                    return_json_type = python_type_to_string(return_annotation)
                    arguments.append({
                        "connection_type": "output",
                        "type": return_json_type
                    })
                    outputs = [param_idx]
                else:
                    outputs = []

                fully_qualified_name = f"{class_name}.{method_name}"

                registry[str(node_id)] = {
                    "arguments": arguments,
                    "inputs": inputs,
                    "outputs": outputs,
                    "node_type": "method",
                    "method_name": fully_qualified_name,
                    "type": fully_qualified_name
                }
                node_id += 1

    return registry


def python_type_to_string(py_type) -> str:
    """Convert Python type annotation to string"""

    # Create reverse mapping from PRIMITIVES_MAP for type lookup
    # This maps Python types to their string representations
    reverse_primitives_map = {v: k for k, v in PRIMITIVES_MAP.items()}

    # Handle empty/missing annotations
    if py_type is inspect.Signature.empty or py_type is None:
        return reverse_primitives_map[Any]

    # Handle basic types using PRIMITIVES_MAP
    if py_type in reverse_primitives_map:
        return reverse_primitives_map[py_type]

    # Default fallback for unknown types
    return reverse_primitives_map[Any]


def save_registry_to_file(filename: str = "registry-py-mwe.json"):
    """Generate and save the registry to a JSON file"""
    registry = generate_registry(FUNCTION_MAP, PRIMITIVES_MAP, CLASS_MAP)

    with open(filename, "w") as f:
        json.dump(registry, f, indent=2)

    print(f"Registry saved to {filename}")
    return registry
