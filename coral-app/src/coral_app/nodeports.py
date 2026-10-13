"""Stage 2: describe every node type's connections — the port table.

One entry per node type, keyed exactly as a graph's ``type`` field (primitives by type name,
functions by name, constructors by class name, methods by ``Class.method``). Each entry lists the
node's input ports and output ports, each a :class:`Port`: a name and an annotation.

Its input is the declarations the plugins hand over (``coral_core.Declaration`` /
``ClassDeclaration``): a callable plus the labels its decorator gave. The ports come from the
callable's signature, with the declared ``annotations`` filling the types it leaves out, ``inputs``
relabelling input ports and ``outputs`` naming output ports — in that order.

This is the single place that derives a node's arity from a callable. Both consumers read it:
``registry.py`` (which turns it into ``node_types.json``) and ``graph.py`` (which validates a graph
against it). They used to introspect separately, which is how they came to disagree about output
numbering.

This module knows callables. It does not know what a graph, an edge, or a registry file is.
"""

import inspect
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, get_args, get_origin

from coral_core import ClassDeclaration, Declaration, MethodDeclaration

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

# Every port is passed by position, so only these parameter kinds can be one.
_POSITIONAL = (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)

PRIMITIVE = "primitive"
FUNCTION = "function"
CONSTRUCTOR = "constructor"
METHOD = "method"


@dataclass(frozen=True)
class Port:
    """One connection of a node type.

    Attributes:
        name: An input's name is its parameter's, unless ``inputs=`` relabels it. An output's is
            the one declared with ``outputs=``, or ``""`` when none is: Python gives a return value
            no name of its own, so there is nothing to read.
        annotation: The declared type, with a missing annotation normalised to ``Any``.
        instance: Whether this is a method's instance, port 0, which the executor checks with
            ``isinstance`` before the call. ``False`` on every other port.
    """

    name: str
    annotation: Any
    instance: bool = False


@dataclass(frozen=True)
class NodePorts:
    """The connections of one node type.

    Attributes:
        kind: One of ``primitive`` / ``function`` / ``constructor`` / ``method``.
        inputs: One :class:`Port` per input port, in port order. For a method, port 0 is the
            instance, named ``self``, annotated with the class itself and marked ``instance``.
        outputs: One :class:`Port` per output port, in port order — 0-based within outputs, which
            is the numbering the editor and the executor use. A callable returning ``None`` has
            none.
        attribute: For a method, the attribute the executor looks up on the instance; ``None`` for
            every other kind. A renamed method's node type no longer contains it.
    """

    kind: str
    inputs: List[Port] = field(default_factory=list)
    outputs: List[Port] = field(default_factory=list)
    attribute: Optional[str] = None


def _annotation(param: inspect.Parameter):
    """Return a parameter's annotation, with a missing one normalised to ``Any``.

    Every consumer treats "annotated ``Any``" and "not annotated" the same way: the registry writes
    ``"any"`` for both, and the graph's edge type check skips both. Collapsing them here spares
    ``graph.py`` from importing ``inspect`` just to recognise ``Signature.empty``.
    """
    if param.annotation is inspect.Signature.empty:
        return Any
    return param.annotation


def _signature(target, node_type: str) -> inspect.Signature:
    """The signature the node's ports are read from.

    Raises:
        ValueError: if there is none to read (a builtin such as ``max``, many C extension
            classes), or a parameter cannot be passed by position — keyword-only, ``*args``,
            ``**kwargs``. The executor passes every port by position, so such a parameter could
            never be wired.
    """
    try:
        sig = inspect.signature(target)
    except (ValueError, TypeError) as error:
        raise ValueError(
            f"Node type {node_type!r}: no signature can be read from {target!r}. Wrap it in a "
            f"Python function or class."
        ) from error

    refused = [param.name for param in sig.parameters.values() if param.kind not in _POSITIONAL]
    if refused:
        raise ValueError(
            f"Node type {node_type!r} has parameters {refused} that cannot be passed by position "
            f"(keyword-only, *args or **kwargs); every port is passed by position."
        )
    return sig


def _parameters(
    sig: inspect.Signature, declaration, node_type: str, *, method: bool, constructor: bool
):
    """The input ports, and the return annotation, after ``annotations=`` and ``inputs=``.

    ``annotations=`` only fills what the signature leaves out, so a declared type never contradicts
    the code. ``inputs=`` relabels the ports it names, and the labels must stay distinct, because
    the editor tells ports apart by them.

    For a method, the first parameter is left out, whatever its name: it is port 0, the instance,
    which the caller adds. It can be neither relabelled nor annotated.

    Raises:
        ValueError: if a method has no parameter to receive its instance, a key names no parameter
            (a method's first included), ``"return"`` is annotated on a constructor, a key's
            parameter is already annotated, or two input ports end up with one label.
    """
    params = list(sig.parameters.values())
    instance = None
    if method:
        if not params:
            raise ValueError(
                f"Node type {node_type!r} has no parameter to receive its instance; a method's "
                f"first parameter is port 0, the instance."
            )
        instance, params = params[0].name, params[1:]
    by_name = {param.name: param for param in params}

    def check_key(option: str, key: str) -> None:
        if key == instance:
            raise ValueError(
                f"Node type {node_type!r}: {option}= names {key!r}, which is port 0, the "
                f"instance; it cannot be relabelled or annotated."
            )
        if key not in by_name:
            raise ValueError(
                f"Node type {node_type!r}: {option}= names {key!r}, which is not a parameter of "
                f"it; its parameters are {list(by_name)}."
            )

    return_annotation = sig.return_annotation
    for key, annotation in declaration.annotations.items():
        if key == "return":
            if constructor:
                raise ValueError(
                    f"Node type {node_type!r}: annotations= cannot type 'return' of a constructor; "
                    f"its output is the instance."
                )
            if sig.return_annotation is not inspect.Signature.empty:
                raise ValueError(
                    f"Node type {node_type!r}: annotations= types 'return', which the code "
                    f"already annotates."
                )
            return_annotation = annotation
            continue
        check_key("annotations", key)
        if by_name[key].annotation is not inspect.Parameter.empty:
            raise ValueError(
                f"Node type {node_type!r}: annotations= types {key!r}, which the code already "
                f"annotates."
            )

    for key in declaration.inputs:
        check_key("inputs", key)

    ports = [
        Port(
            declaration.inputs.get(param.name, param.name),
            declaration.annotations.get(param.name, _annotation(param)),
        )
        for param in params
    ]

    labels = ["self", *[port.name for port in ports]] if method else [p.name for p in ports]
    repeated = sorted({label for label in labels if labels.count(label) > 1})
    if repeated:
        raise ValueError(
            f"Node type {node_type!r}: two input ports are labelled {repeated}; labels must be "
            f"distinct."
        )
    return ports, return_annotation


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


def _output_ports(names, return_annotation, node_type: str) -> List[Port]:
    """One :class:`Port` per output, named by the declaration's ``outputs`` if it gives them.

    The annotation decides how many outputs there are; ``outputs=`` only names them, so the two
    must agree. This is the one check on the names the decorator could not make itself, because it
    needs the annotation.

    Raises:
        ValueError: if the declaration gives a number of names different from its number of
            outputs — including any names at all on a callable that returns nothing.
    """
    annotations = _outputs_from_return(return_annotation, node_type)
    if names is None:
        return [Port("", annotation) for annotation in annotations]

    if len(names) != len(annotations):
        raise ValueError(
            f"Node type {node_type!r} names {len(names)} outputs with outputs={names!r}, but its "
            f"return annotation declares {len(annotations)}. Give one name per output port."
        )
    return [Port(name, annotation) for name, annotation in zip(names, annotations)]


def _function_ports(declaration: Declaration, node_type: str) -> NodePorts:
    """Ports of a plain function: its parameters in, its return annotation out."""
    sig = _signature(declaration.target, node_type)
    inputs, return_annotation = _parameters(
        sig, declaration, node_type, method=False, constructor=False
    )
    return NodePorts(
        kind=FUNCTION,
        inputs=inputs,
        outputs=_output_ports(declaration.outputs, return_annotation, node_type),
    )


def _constructor_ports(declaration: ClassDeclaration, node_type: str) -> NodePorts:
    """Ports of a constructor: the parameters of ``signature(cls)``, which omits ``self``, in; the
    instance out.

    A constructor's single output is the instance, which the registry writes with no output
    argument and so no name.
    """
    sig = _signature(declaration.target, node_type)
    inputs, _ = _parameters(sig, declaration, node_type, method=False, constructor=True)
    return NodePorts(
        kind=CONSTRUCTOR,
        inputs=inputs,
        outputs=[Port("", declaration.target)],
    )


def _method_ports(cls: type, method: MethodDeclaration, node_type: str) -> NodePorts:
    """Ports of a method: the instance at port 0, then the declared parameters.

    The signature of the plain function keeps its first parameter, the instance, whatever it is
    called: exactly the instance-at-port-0 convention. It is re-emitted here as ``self``, annotated
    with ``cls``, so an edge feeding it can be type-checked.
    """
    declaration = method.declaration
    sig = _signature(declaration.target, node_type)
    inputs, return_annotation = _parameters(
        sig, declaration, node_type, method=True, constructor=False
    )
    return NodePorts(
        kind=METHOD,
        inputs=[Port("self", cls, instance=True), *inputs],
        outputs=_output_ports(declaration.outputs, return_annotation, node_type),
        attribute=method.attribute,
    )


def build_port_table(
    function_map: Mapping[str, Declaration] = None,
    class_map: Mapping[str, ClassDeclaration] = None,
    primitives: Mapping[str, type] = None,
) -> Dict[str, NodePorts]:
    """Describe the connections of every node type reachable from the given maps.

    Args:
        function_map: Mapping of function name -> declaration.
        class_map: Mapping of class name -> class declaration; each contributes a constructor entry
            plus one entry per declared method, keyed by its method node type.
        primitives: Mapping of primitive type name -> Python type (i.e. ``PRIMITIVES_MAP``). A
            primitive takes no input and yields one output, its own type.

    Returns:
        Node type -> :class:`NodePorts`, inserted primitives first, then functions, constructors and
        methods.

    Raises:
        DuplicateNodeTypeError: if one name is claimed by two declared node types — a primitive, a
            function, a constructor or a method — since this is the only place the surfaces meet.
            A method is declared with ``plugin.method``, so a dotted function name equal to its
            ``Class.method`` key is two claims on one name, like any other. Also raised for one
            class registered under two keys: a class is named by its key, so it would have two
            names.
        ValueError: if any callable returns a tuple without declaring its elements — see
            :func:`_outputs_from_return`. This fires while the table is built, so a badly annotated
            function in an installed plugin fails the host rather than yielding a wrong registry.
            Also raised, for the same reason, if a callable has no readable signature or a
            parameter that cannot be passed by position, or its declaration's labels do not fit
            it — see :func:`_signature`, :func:`_parameters` and :func:`_output_ports`.
    """
    table: Dict[str, NodePorts] = {}

    def put(node_type: str, ports: NodePorts) -> None:
        # Two node types under one name are a bad configuration and are refused: a graph names only
        # the node type, so whichever entry won would decide what the graph computes while the JSON
        # looks identical. Stage 1 cannot catch this one, because it merges the function and class
        # surfaces into separate maps.
        if node_type in table:
            raise DuplicateNodeTypeError(
                f"node type {node_type!r} is declared as both a {table[node_type].kind} and a "
                f"{ports.kind}"
            )
        table[node_type] = ports

    for prim_name, prim_type in (primitives or {}).items():
        put(prim_name, NodePorts(kind=PRIMITIVE, inputs=[], outputs=[Port("", prim_type)]))

    for func_name, declaration in (function_map or {}).items():
        put(func_name, _function_ports(declaration, func_name))

    # One class, one key: the key is the class's name wherever the class types a port.
    registered_as: Dict[type, str] = {}
    for class_name, declaration in (class_map or {}).items():
        cls = declaration.target
        if cls in registered_as:
            raise DuplicateNodeTypeError(
                f"class {cls.__name__!r} is registered as both {registered_as[cls]!r} and "
                f"{class_name!r}"
            )
        registered_as[cls] = class_name
        put(class_name, _constructor_ports(declaration, class_name))

    for declaration in (class_map or {}).values():
        for node_type, method in declaration.methods.items():
            put(node_type, _method_ports(declaration.target, method, node_type))

    return table


def methods_of(port_table: Mapping[str, NodePorts], class_name: str) -> List[str]:
    """The ``Class.method`` keys the table holds for one class, in table order."""
    prefix = f"{class_name}."
    return [
        node_type
        for node_type, ports in port_table.items()
        if ports.kind == METHOD and node_type.startswith(prefix)
    ]
