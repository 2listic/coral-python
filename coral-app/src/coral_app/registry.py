import inspect
import json
from typing import Any, Dict, List, Optional

from coral_app import PRIMITIVES_MAP, TYPE_NAMES, build_class_map, build_function_map, discover
from coral_app.nodeports import NodePorts, build_port_table, methods_of

# Python type -> the name the file format uses for it, for the socket types written on every
# argument. Built from `TYPE_NAMES`, not from `PRIMITIVES_MAP`: the collections are renderable type
# names without being node types, so more types can appear on a socket than can be a node.
_TYPE_NAME_OF = {v: k for k, v in TYPE_NAMES.items()}


def _create_input_argument(param_name: str, type_annotation) -> Dict:
    """Create an input argument dictionary"""
    return {
        "connection_type": "input",
        "type": python_type_to_string(type_annotation),
        "name": param_name,
    }


def _create_output_argument(type_annotation) -> Dict:
    """Create an output argument dictionary"""
    return {"connection_type": "output", "type": python_type_to_string(type_annotation), "name": ""}


def _number_inputs(ports: NodePorts):
    """Number a node's input ports for the file format.

    Returns:
        tuple: (input_arguments, input_indices) — indices are 0-based, one per input port.
    """
    arguments = [_create_input_argument(name, annotation) for name, annotation in ports.inputs]
    return arguments, list(range(len(ports.inputs)))


def _number_outputs(ports: NodePorts, first_idx: int):
    """Number a node's output ports for the file format.

    The file format numbers outputs in a per-node index space that *continues after the inputs*, so
    the caller passes the first free index. (The editor and the executor number outputs 0-based
    within outputs; that difference is deliberate and confined to this file.)

    Returns:
        tuple: (output_arguments, output_indices)
    """
    arguments = [_create_output_argument(annotation) for annotation in ports.outputs]
    return arguments, list(range(first_idx, first_idx + len(ports.outputs)))


def _add_function_node(registry: Dict, func_name: str, ports: NodePorts) -> None:
    """Add a function node to the registry, keyed by its name."""
    arguments, inputs = _number_inputs(ports)
    output_arguments, outputs = _number_outputs(ports, len(inputs))
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


def _add_constructor(registry: Dict, class_name: str, ports: NodePorts) -> None:
    """Add a constructor node to the registry, keyed by the class name.

    The instance a constructor produces is written as ``outputs: [-1]`` with no output argument —
    the file format's convention for "one unnamed output".
    """
    arguments, inputs = _number_inputs(ports)

    registry[class_name] = {
        "arguments": arguments,
        "inputs": inputs,
        "outputs": [-1],
        "node_type": "constructor",
        "type": class_name,
    }


def _add_methods(registry: Dict, class_name: str, port_table: Dict[str, NodePorts]) -> None:
    """Add all public methods of a class to the registry, keyed by 'Class.method'.

    Which methods exist, and that the instance occupies input port 0, both come from the port
    table.
    """
    for fully_qualified_name in methods_of(port_table, class_name):
        ports = port_table[fully_qualified_name]

        arguments, inputs = _number_inputs(ports)
        output_arguments, outputs = _number_outputs(ports, len(inputs))
        arguments.extend(output_arguments)

        registry[fully_qualified_name] = {
            "arguments": arguments,
            "inputs": inputs,
            "outputs": outputs,
            "node_type": "method",
            "type": fully_qualified_name,
        }


def generate_registry(
    function_map: Dict[str, callable],
    primitives: List[str] = None,
    class_map: Dict[str, type] = None,
) -> Dict:
    """Generate the node registry in the DealiiX platform format.

    Describes the given function/class maps as a port table (stage 2) and renders it into a dict
    keyed by each node's ``type`` string (primitives by type name, functions by name, constructors
    by class name, methods by ``Class.method``). Everything about the *file format* — argument
    dicts, index numbering, the ``[-1]`` convention — is decided here; the arity and annotations
    come from the port table, which the executor reads too.

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

    # One entry per node type, describing its connections. Note the emission loops below iterate the
    # *maps*, never the table: the key order of `node_types.json` is part of the contract, and the
    # table is only ever a lookup.
    port_table = build_port_table(function_map=function_map, class_map=class_map)

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
    for func_name in function_map:
        _add_function_node(registry, func_name, port_table[func_name])

    # Add class constructors and methods
    if class_map:
        for class_name in class_map:
            _add_constructor(registry, class_name, port_table[class_name])

        for class_name in class_map:
            _add_methods(registry, class_name, port_table)

    return registry


def python_type_to_string(py_type) -> str:
    """Convert Python type annotation to string"""

    # Handle empty/missing annotations
    if py_type is inspect.Signature.empty or py_type is None:
        return _TYPE_NAME_OF[Any]

    # Handle the named types: the primitives plus the collections
    if py_type in _TYPE_NAME_OF:
        return _TYPE_NAME_OF[py_type]

    # Default fallback for unknown types. A parameterised generic such as `List[int]` lands here
    # too: only the bare `list` is a name the format knows.
    return _TYPE_NAME_OF[Any]


def save_registry_to_file(filename: str = "registry-py.json", plugins: Optional[List[str]] = None):
    """Generate and save the registry to a JSON file

    Args:
        filename: Output path for the registry file
        plugins: List of plugin names to include. If None, includes every discovered plugin.
    """
    # None means "every discovered plugin" — the host never names a specific plugin.
    if plugins is None:
        plugins = discover()

    # Build function and class maps based on the specified plugins
    function_map = build_function_map(include=plugins)
    class_map = build_class_map(include=plugins)

    # Always include primitives
    registry = generate_registry(function_map, list(PRIMITIVES_MAP.keys()), class_map)

    with open(filename, "w") as f:
        json.dump(registry, f, indent=2)

    print(f"Registry saved to {filename}")
    print(f"Loaded plugins: {', '.join(plugins)}")
    return registry
