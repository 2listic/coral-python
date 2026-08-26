"""Stage 2: describe every node type's connections — the port table.

One entry per node type, keyed exactly as a graph's ``type`` field (primitives by type name,
functions by name, constructors by class name, methods by ``Class.method``). Each entry lists the
node's input parameters (name and annotation) and its outputs (annotations).

This is the single place that derives a node's arity from a callable. Both consumers read it:
``registry.py`` (which turns it into ``node_types.json``) and ``graph.py`` (which validates a graph
against it). They used to introspect separately, which is how they came to disagree about output
numbering.

This module knows callables. It does not know what a graph, an edge, or a registry file is.
"""

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Tuple, get_args, get_origin

from coral_app.errors import DuplicateNodeTypeError

__all__ = [
    "CONSTRUCTOR",
    "FUNCTION",
    "METHOD",
    "PRIMITIVE",
    "NodePorts",
    "build_port_table",
    "methods_of",
]

PRIMITIVE = "primitive"
FUNCTION = "function"
CONSTRUCTOR = "constructor"
METHOD = "method"


@dataclass(frozen=True)
class NodePorts:
    """The connections of one node type.

    Attributes:
        kind: One of ``primitive`` / ``function`` / ``constructor`` / ``method``.
        inputs: One ``(name, annotation)`` per input port, in port order. For a method, port 0 is
            the instance, named ``self`` and annotated with the class itself.
        outputs: One annotation per output port, in port order — 0-based within outputs, which is
            the numbering the editor and the executor use. A callable returning ``None`` has none.
    """

    kind: str
    inputs: List[Tuple[str, Any]] = field(default_factory=list)
    outputs: List[Any] = field(default_factory=list)


def _annotation(param: inspect.Parameter):
    """Return a parameter's annotation, with a missing one normalised to ``Any``.

    Every consumer treats "annotated ``Any``" and "not annotated" the same way: the registry writes
    ``"any"`` for both, and the graph's edge type check skips both. Collapsing them here spares
    ``graph.py`` from importing ``inspect`` just to recognise ``Signature.empty``.
    """
    if param.annotation is inspect.Signature.empty:
        return Any
    return param.annotation


def _outputs_from_return(return_annotation) -> List[Any]:
    """Turn a return annotation into one annotation per output port.

    A ``Tuple[...]`` return is one output per element; ``None`` (or a missing annotation) is no
    output at all; anything else is a single output.
    """
    if get_origin(return_annotation) is tuple:
        return list(get_args(return_annotation))

    if (
        return_annotation is not None
        and return_annotation is not type(None)
        and return_annotation is not inspect.Signature.empty
    ):
        return [return_annotation]

    return []


def _public_method_names(cls: type) -> List[str]:
    """Names of the class's public, pure-Python instance methods, in ``dir()`` order.

    C extension methods are not ``inspect.isfunction``, so a C extension class yields none — the
    documented limitation that such classes register a constructor but no methods.
    """
    names = []
    for method_name in dir(cls):
        if method_name.startswith("_"):
            continue
        method = getattr(cls, method_name)
        if not callable(method) or not inspect.isfunction(method):
            continue
        names.append(method_name)
    return names


def _function_ports(func: Callable) -> NodePorts:
    """Ports of a plain function: its parameters in, its return annotation out."""
    sig = inspect.signature(func)
    return NodePorts(
        kind=FUNCTION,
        inputs=[(name, _annotation(param)) for name, param in sig.parameters.items()],
        outputs=_outputs_from_return(sig.return_annotation),
    )


def _constructor_ports(cls: type) -> NodePorts:
    """Ports of a constructor: ``__init__`` parameters in, the instance out.

    ``signature(cls)`` already omits ``self``. It refuses outright on a C extension type
    (``ValueError: no signature found for builtin type``), so those fall back to reading
    ``__init__`` and dropping ``self`` by name — which is how this was always derived.

    That fallback keeps a C extension class from raising here, but its entry is a placeholder rather
    than a usable constructor: the class defines no ``__init__`` of its own, so this reads
    ``object``'s and records two ``Any`` inputs named ``args``/``kwargs``. A pure-Python wrapper
    class is the way to expose such a type properly.
    """
    try:
        params = list(inspect.signature(cls).parameters.items())
    except (ValueError, TypeError):
        params = [
            (name, param)
            for name, param in inspect.signature(cls.__init__).parameters.items()
            if name != "self"
        ]

    return NodePorts(
        kind=CONSTRUCTOR,
        inputs=[(name, _annotation(param)) for name, param in params],
        outputs=[cls],
    )


def _method_ports(cls: type, method_name: str) -> NodePorts:
    """Ports of a method: the instance at port 0, then the declared parameters.

    ``signature(cls.method)`` keeps ``self``, which is exactly the instance-at-port-0 convention;
    it is re-emitted here annotated with ``cls`` so an edge feeding it can be type-checked.
    """
    sig = inspect.signature(getattr(cls, method_name))
    inputs = [("self", cls)]
    inputs.extend(
        (name, _annotation(param)) for name, param in sig.parameters.items() if name != "self"
    )
    return NodePorts(
        kind=METHOD, inputs=inputs, outputs=_outputs_from_return(sig.return_annotation)
    )


def build_port_table(
    function_map: Mapping[str, Callable] = None,
    class_map: Mapping[str, type] = None,
    primitives: Mapping[str, type] = None,
) -> Dict[str, NodePorts]:
    """Describe the connections of every node type reachable from the given maps.

    Args:
        function_map: Mapping of function name -> callable.
        class_map: Mapping of class name -> class; each contributes a constructor entry plus one
            entry per public method, keyed ``Class.method``.
        primitives: Mapping of primitive type name -> Python type (i.e. ``PRIMITIVES_MAP``). A
            primitive takes no input and yields one output, its own type.

    Returns:
        Node type -> :class:`NodePorts`, inserted primitives first, then functions, constructors and
        methods.

    Raises:
        DuplicateNodeTypeError: if one name is claimed by two declared node types — a primitive, a
            function and a constructor all key the table by a bare name, and this is the only place
            the three surfaces meet. A ``Class.method`` key colliding with a function or constructor
            of the same name is *not* an error: see ``put`` below.
    """
    table: Dict[str, NodePorts] = {}

    def put(node_type: str, ports: NodePorts) -> None:
        # A collision between two *declared* node types — primitive, function or constructor — is a
        # bad configuration and is refused: a graph names only the node type, so whichever entry won
        # would decide what the graph computes while the JSON looks identical. Stage 1 cannot catch
        # this one, because it merges the function and class surfaces into separate maps.
        #
        # A collision involving a *method* entry keeps first-writer-wins, which is what the
        # insertion order above is for: it makes a dotted function name such as `math.sqrt` stay a
        # function even if some class `math` also had a `sqrt` method. A method key is derived from a
        # class the host was handed, not declared by anyone, so there is no competing claim to refuse.
        existing = table.get(node_type)
        if existing is not None:
            if METHOD in (existing.kind, ports.kind):
                return
            raise DuplicateNodeTypeError(
                f"node type {node_type!r} is declared as both a {existing.kind} and a {ports.kind}"
            )
        table[node_type] = ports

    for prim_name, prim_type in (primitives or {}).items():
        put(prim_name, NodePorts(kind=PRIMITIVE, inputs=[], outputs=[prim_type]))

    for func_name, func in (function_map or {}).items():
        put(func_name, _function_ports(func))

    for class_name, cls in (class_map or {}).items():
        put(class_name, _constructor_ports(cls))

    for class_name, cls in (class_map or {}).items():
        for method_name in _public_method_names(cls):
            put(f"{class_name}.{method_name}", _method_ports(cls, method_name))

    return table


def methods_of(port_table: Mapping[str, NodePorts], class_name: str) -> List[str]:
    """The ``Class.method`` keys the table holds for one class, in table order."""
    prefix = f"{class_name}."
    return [
        node_type
        for node_type, ports in port_table.items()
        if ports.kind == METHOD and node_type.startswith(prefix)
    ]
