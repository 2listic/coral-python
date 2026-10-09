"""Stage 2: describe every node type's connections — the port table.

One entry per node type, keyed exactly as a graph's ``type`` field (primitives by type name,
functions by name, constructors by class name, methods by ``Class.method``). Each entry lists the
node's input ports and output ports, each a :class:`Port`: a name and an annotation.

This is the single place that derives a node's arity from a callable. Both consumers read it:
``registry.py`` (which turns it into ``node_types.json``) and ``graph.py`` (which validates a graph
against it). They used to introspect separately, which is how they came to disagree about output
numbering.

This module knows callables. It does not know what a graph, an edge, or a registry file is.
"""

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Mapping, get_args, get_origin

from coral_core import output_names

from coral_app.errors import DuplicateNodeTypeError

__all__ = [
    "CONSTRUCTOR",
    "FUNCTION",
    "METHOD",
    "PRIMITIVE",
    "NodePorts",
    "Port",
    "build_port_table",
    "methods_of",
]

PRIMITIVE = "primitive"
FUNCTION = "function"
CONSTRUCTOR = "constructor"
METHOD = "method"


@dataclass(frozen=True)
class Port:
    """One connection of a node type.

    Attributes:
        name: An input's name is its parameter's. An output's is the one declared with
            ``coral_core.outputs``, or ``""`` when none is: Python gives a return value no name of
            its own, so there is nothing to read.
        annotation: The declared type, with a missing annotation normalised to ``Any``.
    """

    name: str
    annotation: Any


@dataclass(frozen=True)
class NodePorts:
    """The connections of one node type.

    Attributes:
        kind: One of ``primitive`` / ``function`` / ``constructor`` / ``method``.
        inputs: One :class:`Port` per input port, in port order. For a method, port 0 is the
            instance, named ``self`` and annotated with the class itself.
        outputs: One :class:`Port` per output port, in port order — 0-based within outputs, which
            is the numbering the editor and the executor use. A callable returning ``None`` has
            none.
    """

    kind: str
    inputs: List[Port] = field(default_factory=list)
    outputs: List[Port] = field(default_factory=list)


def _annotation(param: inspect.Parameter):
    """Return a parameter's annotation, with a missing one normalised to ``Any``.

    Every consumer treats "annotated ``Any``" and "not annotated" the same way: the registry writes
    ``"any"`` for both, and the graph's edge type check skips both. Collapsing them here spares
    ``graph.py`` from importing ``inspect`` just to recognise ``Signature.empty``.
    """
    if param.annotation is inspect.Signature.empty:
        return Any
    return param.annotation


def _input_ports(params: Iterable[inspect.Parameter]) -> List[Port]:
    """One :class:`Port` per parameter, in order; a missing annotation becomes ``Any``."""
    return [Port(param.name, _annotation(param)) for param in params]


def _outputs_from_return(return_annotation, node_type: str) -> List[Any]:
    """Turn a return annotation into one annotation per output port.

    A ``Tuple[...]`` return is one output per element; ``None`` (or a missing annotation) is no
    output at all; anything else is a single output — including plain ``tuple``, which is *one*
    output that happens to carry a tuple.

    A tuple return must declare its elements, so the spellings that do not are rejected here rather
    than silently mis-described:

    - ``Tuple`` and ``Tuple[()]`` carry no arguments and would yield **zero** ports, reading as "no
      outputs" when the author meant "returns a tuple". Every outgoing edge would then fail graph
      check 7 with a message about ports, when the fault is the annotation.
    - ``Tuple[Any, ...]`` is variadic: it has no static arity for the port table to record, and
      would yield a second port annotated ``Ellipsis`` — which the registry renders as a socket type
      and the edge type check reasons about.

    Args:
        return_annotation: The callable's return annotation.
        node_type: The node type this annotation belongs to, used only to name the offender.

    Raises:
        ValueError: if the return annotation is a tuple that does not declare its elements.
    """
    if get_origin(return_annotation) is tuple:
        args = get_args(return_annotation)
        if not args or Ellipsis in args:
            raise ValueError(
                f"Node type {node_type!r} returns {return_annotation!r}, which does not declare "
                f"its output ports. Write the elements out, e.g. Tuple[float, str] — or plain "
                f"`tuple` for a single output carrying a tuple."
            )
        return list(args)

    if (
        return_annotation is not None
        and return_annotation is not type(None)
        and return_annotation is not inspect.Signature.empty
    ):
        return [return_annotation]

    return []


def _output_ports(func: Callable, return_annotation, node_type: str) -> List[Port]:
    """One :class:`Port` per output, named by the callable's ``@outputs`` declaration if it has one.

    The annotation decides how many outputs there are; ``@outputs`` only names them, so the two
    must agree. This is the one check on the names the decorator could not make itself, because it
    needs the annotation.

    Raises:
        ValueError: if the callable declares a number of names different from its number of
            outputs — including any names at all on a callable that returns nothing.
    """
    annotations = _outputs_from_return(return_annotation, node_type)
    names = output_names(func)
    if names is None:
        return [Port("", annotation) for annotation in annotations]

    if len(names) != len(annotations):
        raise ValueError(
            f"Node type {node_type!r} names {len(names)} outputs with @outputs{names!r}, but its "
            f"return annotation declares {len(annotations)}. Give one name per output port."
        )
    return [Port(name, annotation) for name, annotation in zip(names, annotations)]


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


def _function_ports(func: Callable, node_type: str) -> NodePorts:
    """Ports of a plain function: its parameters in, its return annotation out."""
    sig = inspect.signature(func)
    return NodePorts(
        kind=FUNCTION,
        inputs=_input_ports(sig.parameters.values()),
        outputs=_output_ports(func, sig.return_annotation, node_type),
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

    A constructor's single output is the instance, which the registry writes with no output
    argument and so no name. An ``__init__`` marked with ``@outputs`` is therefore refused rather
    than ignored — including one a subclass inherits, since it is the same function.

    Raises:
        ValueError: if the class's ``__init__`` is marked with ``@outputs``.
    """
    if output_names(cls.__init__) is not None:
        raise ValueError(
            f"Class {cls.__name__!r} marks __init__ with @outputs, but a constructor's output "
            f"cannot be named: it is the instance, which carries no name. Remove the decorator."
        )

    try:
        params = inspect.signature(cls).parameters.values()
    except (ValueError, TypeError):
        params = [
            param
            for param in inspect.signature(cls.__init__).parameters.values()
            if param.name != "self"
        ]

    return NodePorts(
        kind=CONSTRUCTOR,
        inputs=_input_ports(params),
        outputs=[Port("", cls)],
    )


def _method_ports(cls: type, method_name: str, node_type: str) -> NodePorts:
    """Ports of a method: the instance at port 0, then the declared parameters.

    ``signature(cls.method)`` keeps ``self``, which is exactly the instance-at-port-0 convention;
    it is re-emitted here annotated with ``cls`` so an edge feeding it can be type-checked.
    """
    method = getattr(cls, method_name)
    sig = inspect.signature(method)
    others = (param for param in sig.parameters.values() if param.name != "self")
    return NodePorts(
        kind=METHOD,
        inputs=[Port("self", cls), *_input_ports(others)],
        outputs=_output_ports(method, sig.return_annotation, node_type),
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
            of the same name is *not* an error: see ``put`` below. Also raised for one class
            registered under two keys: a class is named by its key, so it would have two names.
        ValueError: if any callable returns a tuple without declaring its elements — see
            :func:`_outputs_from_return`. This fires while the table is built, so a badly annotated
            function in an installed plugin fails the host rather than yielding a wrong registry.
            Also raised, for the same reason, if a callable's ``@outputs`` names do not match its
            number of outputs, or a class's ``__init__`` carries ``@outputs``.
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
        put(prim_name, NodePorts(kind=PRIMITIVE, inputs=[], outputs=[Port("", prim_type)]))

    for func_name, func in (function_map or {}).items():
        put(func_name, _function_ports(func, func_name))

    # One class, one key: the key is the class's name wherever the class types a port.
    registered_as: Dict[type, str] = {}
    for class_name, cls in (class_map or {}).items():
        if cls in registered_as:
            raise DuplicateNodeTypeError(
                f"class {cls.__name__!r} is registered as both {registered_as[cls]!r} and "
                f"{class_name!r}"
            )
        registered_as[cls] = class_name
        put(class_name, _constructor_ports(cls))

    for class_name, cls in (class_map or {}).items():
        for method_name in _public_method_names(cls):
            node_type = f"{class_name}.{method_name}"
            put(node_type, _method_ports(cls, method_name, node_type))

    return table


def methods_of(port_table: Mapping[str, NodePorts], class_name: str) -> List[str]:
    """The ``Class.method`` keys the table holds for one class, in table order."""
    prefix = f"{class_name}."
    return [
        node_type
        for node_type, ports in port_table.items()
        if ports.kind == METHOD and node_type.startswith(prefix)
    ]
