import json
import inspect
from typing import Any, Dict, List, get_origin, get_args, Optional

from coral_app import PRIMITIVES_MAP, build_function_map, build_class_map, discover

# Reverse mapping for type-to-string conversion during registry generation
_REVERSE_PRIMITIVES_MAP = {v: k for k, v in PRIMITIVES_MAP.items()}


def _create_input_argument(param_name: str, type_annotation) -> Dict:
    """Create an input argument dictionary"""
    return {
        "connection_type": "input",
        "type": python_type_to_string(type_annotation),
        "name": param_name
    }


def _create_output_argument(type_annotation) -> Dict:
    """Create an output argument dictionary"""
    return {
        "connection_type": "output",
        "type": python_type_to_string(type_annotation),
        "name": ""
    }


def _process_return_type(return_annotation, param_idx: int):
    """Process return type and generate output arguments and indices.

    Returns:
        tuple: (output_arguments, output_indices)
    """
    origin = get_origin(return_annotation)

    # Handle Tuple return types - create separate output for each element
    if origin is tuple:
        tuple_args = get_args(return_annotation)
        output_arguments = [_create_output_argument(t) for t in tuple_args]
        output_indices = list(range(param_idx, param_idx + len(tuple_args)))
        return output_arguments, output_indices

    # Handle single return value (not None)
    if (return_annotation is not None
        and return_annotation != type(None)
        and return_annotation != inspect.Signature.empty):
        return [_create_output_argument(return_annotation)], [param_idx]

    # No return value
    return [], []


def _add_function_node(registry: Dict, func_name: str, func: callable) -> None:
    """Add a function node to the registry, keyed by its name."""
    sig = inspect.signature(func)

    # Process input parameters
    arguments = []
    inputs = []
    for param_idx, (param_name, param) in enumerate(sig.parameters.items()):
        arguments.append(_create_input_argument(param_name, param.annotation))
        inputs.append(param_idx)

    # Process return type
    param_idx = len(sig.parameters)
    output_arguments, outputs = _process_return_type(sig.return_annotation, param_idx)
    arguments.extend(output_arguments)

    # `type` is the function name — the single node identifier (the editor looks entries up as
    # registry[type], and graphs reference nodes by type).
    registry[func_name] = {
        "arguments": arguments,
        "inputs": inputs,
        "outputs": outputs,
        "node_type": "function",
        "type": func_name,
    }


def _add_constructor(registry: Dict, class_name: str, cls: type) -> None:
    """Add a constructor node to the registry, keyed by the class name."""
    init_sig = inspect.signature(cls.__init__)

    # Process constructor parameters (skip 'self')
    arguments = []
    inputs = []
    param_idx = 0
    for param_name, param in init_sig.parameters.items():
        if param_name == 'self':
            continue

        arguments.append(_create_input_argument(param_name, param.annotation))
        inputs.append(param_idx)
        param_idx += 1

    registry[class_name] = {
        "arguments": arguments,
        "inputs": inputs,
        "outputs": [-1],
        "node_type": "constructor",
        "type": class_name,
    }


def _add_methods(registry: Dict, class_name: str, cls: type) -> None:
    """Add all public methods of a class to the registry, keyed by 'Class.method'."""
    for method_name in dir(cls):
        # Skip private and dunder methods
        if method_name.startswith('_'):
            continue

        method = getattr(cls, method_name)
        if not callable(method) or not inspect.isfunction(method):
            continue

        sig = inspect.signature(method)

        # First input: the instance itself
        arguments = [_create_input_argument("self", class_name)]
        inputs = [0]
        param_idx = 1

        # Process method parameters (skip 'self')
        for param_name, param in sig.parameters.items():
            if param_name == 'self':
                continue

            arguments.append(_create_input_argument(param_name, param.annotation))
            inputs.append(param_idx)
            param_idx += 1

        # Process return type
        output_arguments, outputs = _process_return_type(sig.return_annotation, param_idx)
        arguments.extend(output_arguments)

        fully_qualified_name = f"{class_name}.{method_name}"

        registry[fully_qualified_name] = {
            "arguments": arguments,
            "inputs": inputs,
            "outputs": outputs,
            "node_type": "method",
            "type": fully_qualified_name,
        }


def generate_registry(
    function_map: Dict[str, callable], primitives: List[str] = None, class_map: Dict[str, type] = None
) -> Dict:
    """Generate the node registry in the DealiiX platform format.

    Introspects the given function/class maps and primitive type names and returns a dict keyed by
    each node's ``type`` string (primitives by type name, functions by name, constructors by class
    name, methods by ``Class.method``).

    Args:
        function_map: Mapping of function name -> callable.
        primitives: List of primitive type names to include (always added).
        class_map: Optional mapping of class name -> class (adds constructors and methods).

    Returns:
        The registry dict keyed by node ``type``.

    Raises:
        ValueError: if ``primitives`` or ``function_map`` is None.
    """

    if primitives is None or function_map is None:
        raise ValueError("primitives and function_map must be provided")

    registry = {}

    # Add primitive types, keyed by the primitive type name. Primitives take no inputs, but the
    # empty `arguments` list is required: the platform's registry validator skips any entry lacking
    # an `arguments` key.
    for prim_type in primitives:
        registry[prim_type] = {
            "arguments": [],
            "value": "",
            "inputs": [],
            "outputs": [-1],
            "node_type": "primitive",
            "type": prim_type,
        }

    # Add functions
    for func_name, func in function_map.items():
        _add_function_node(registry, func_name, func)

    # Add class constructors and methods
    if class_map:
        for class_name, cls in class_map.items():
            _add_constructor(registry, class_name, cls)

        for class_name, cls in class_map.items():
            _add_methods(registry, class_name, cls)

    return registry


def python_type_to_string(py_type) -> str:
    """Convert Python type annotation to string"""

    # Handle empty/missing annotations
    if py_type is inspect.Signature.empty or py_type is None:
        return _REVERSE_PRIMITIVES_MAP[Any]

    # Handle basic types using PRIMITIVES_MAP
    if py_type in _REVERSE_PRIMITIVES_MAP:
        return _REVERSE_PRIMITIVES_MAP[py_type]

    # Default fallback for unknown types
    return _REVERSE_PRIMITIVES_MAP[Any]


def save_registry_to_file(filename: str = "registry-py.json", modules: Optional[List[str]] = None):
    """Generate and save the registry to a JSON file

    Args:
        filename: Output path for the registry file
        modules: List of module names to include. If None, includes every discovered plugin.
    """
    # None means "every discovered plugin" — the host never names a specific plugin.
    if modules is None:
        modules = discover()

    # Build function and class maps based on specified modules
    function_map = build_function_map(include=modules)
    class_map = build_class_map(include=modules)

    # Always include primitives
    registry = generate_registry(function_map, list(PRIMITIVES_MAP.keys()), class_map)

    with open(filename, "w") as f:
        json.dump(registry, f, indent=2)

    print(f"Registry saved to {filename}")
    print(f"Loaded modules: {', '.join(modules)}")
    return registry
