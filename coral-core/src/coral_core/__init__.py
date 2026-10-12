"""coral-core — the shared contract for the coral plugin system.

A plugin is an instance of :class:`Plugin`. A function, a class or a method becomes a node type by
being declared on it with one of three decorators, which also carry every option about that node::

    plugin = Plugin()

    @plugin.function
    def add(a: float, b: float) -> float: ...

    @plugin.cls
    class Calculator:
        def __init__(self, initial_value: float): ...

        @plugin.method(outputs="value")
        def get_value(self) -> float: ...

A callable that cannot be decorated where it is defined — a builtin, a class from another library —
is declared with the same decorators used as a plain call: ``plugin.function(math.atan2, ...)``.

The options are labels only, and they are kept in the plugin, never on the decorated object: a
builtin has no ``__dict__`` to write to, and a label stored on a function two plugins both declare
would let one overwrite the other. What the host receives are declarations — :class:`Declaration`,
:class:`ClassDeclaration` — each a callable together with what its decorator said. Reading a
signature and building ports from it is the host's job, not this package's.

The entry-point name under which a plugin registers (see the host's ``coral.plugins`` group) is the
plugin's identity — the contract carries no ``name``.

This package depends on nothing internal: plugins and the host both import it, it imports neither.
"""

import inspect
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Callable, Mapping

__all__ = [
    "ClassDeclaration",
    "Declaration",
    "MethodDeclaration",
    "Plugin",
]

# A class's constructor is the class's own node type, so neither can be declared as a method.
_CONSTRUCTORS = ("__init__", "__new__")


@dataclass(frozen=True)
class Declaration:
    """A function or method node type: the callable, and what its decorator said about it.

    Read-only throughout: ``inputs`` and ``annotations`` are read-only views of private copies,
    so a host holding a declaration cannot change the plugin it came from.

    Attributes:
        target: The callable the node runs.
        inputs: ``{parameter: label}`` for the input ports to relabel; the others keep their
            parameter's name.
        outputs: The output names in port order, or ``None`` when none were given.
        annotations: Types for the parameters (key ``"return"`` for the return value) that the
            signature leaves unannotated.
    """

    target: Callable
    inputs: Mapping[str, str] = field(default_factory=dict)
    outputs: tuple[str, ...] | None = None
    annotations: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _freeze(self, "inputs", "annotations")


@dataclass(frozen=True)
class MethodDeclaration:
    """One method node type of a class.

    Attributes:
        attribute: The attribute the method is reached by on an instance. The host looks it up on
            the instance at run time, so an override in the instance's own class is what runs.
        declaration: The function the class holds under that attribute, with its labels.
    """

    attribute: str
    declaration: Declaration


@dataclass(frozen=True)
class ClassDeclaration:
    """A registered class: its constructor node type and its method node types.

    The constructor is the class's own node type, so the class carries the constructor's options
    itself. It has no ``outputs``: a constructor's single output is the instance, which carries no
    name.

    Attributes:
        target: The class.
        inputs: ``{parameter: label}`` for the constructor's input ports.
        annotations: Types for the constructor's parameters that its signature leaves unannotated.
        methods: ``{method node name: MethodDeclaration}``, keyed by the full node name
            (``"Calculator.get_value"``), sorted by attribute name.
    """

    target: type
    inputs: Mapping[str, str] = field(default_factory=dict)
    annotations: Mapping[str, Any] = field(default_factory=dict)
    methods: dict[str, MethodDeclaration] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _freeze(self, "inputs", "annotations", "methods")


@dataclass(frozen=True)
class _Mark:
    """What ``Plugin.method`` was told about one function, before any class is known."""

    name: str | None
    inputs: dict[str, str]
    outputs: tuple[str, ...] | None
    annotations: dict[str, Any]


class Plugin:
    """A set of node types, declared with :meth:`function`, :meth:`cls` and :meth:`method`.

    Each decorator can be used three ways, and returns its target unchanged in all of them::

        @plugin.function                    # bare
        @plugin.function(name="math.pow")   # with options
        plugin.function(math.atan2, ...)    # as a call, on an object defined elsewhere

    Every instance holds its own declarations; there is no global registry.
    """

    def __init__(self) -> None:
        self._functions: dict[str, Declaration] = {}
        # class key -> its declaration without methods; `classes()` resolves those
        self._classes: dict[str, ClassDeclaration] = {}
        self._class_keys: dict[type, str] = {}
        # marked function -> its labels. Keyed by the function, because which classes it belongs
        # to is only known once every class has been registered.
        self._marks: dict[Callable, _Mark] = {}

    def function(
        self,
        target: Callable | None = None,
        /,
        *,
        name: str | None = None,
        inputs: dict[str, str] | None = None,
        outputs: str | tuple[str, ...] | list[str] | None = None,
        annotations: dict[str, Any] | None = None,
    ):
        """Declare a function node type.

        Args:
            target: Any callable that is not a class. Omitted when used as ``@plugin.function(...)``.
            name: The node type; defaults to the callable's ``__name__``. May contain ``.``, as in
                ``math.sqrt``.
            inputs: ``{parameter: label}`` relabelling some input ports.
            outputs: The output names in port order; a plain ``str`` is one name.
            annotations: Types for parameters (and ``"return"``) the signature leaves unannotated.

        Raises:
            TypeError: if the target is a class or not callable, or an option has the wrong type.
            ValueError: if an option's value is refused, or the name is already declared here.
        """

        def declare(func: Callable) -> Callable:
            where = f"plugin.function({_describe(func)})"
            if not callable(func) or isinstance(func, type):
                raise TypeError(
                    f"{where}: a function node needs a callable that is not a class; "
                    f"declare a class with plugin.cls"
                )
            node_type = _name(name, func, where, dotted=True)
            self._claim(node_type, where)
            self._functions[node_type] = Declaration(
                func,
                _inputs(inputs, where),
                _outputs(outputs, where),
                _annotations(annotations, where),
            )
            return func

        return declare if target is None else declare(target)

    def cls(
        self,
        target: type | None = None,
        /,
        *,
        name: str | None = None,
        inputs: dict[str, str] | None = None,
        annotations: dict[str, Any] | None = None,
    ):
        """Declare a class: its constructor becomes a node type, keyed by the class's name.

        Only the methods declared with :meth:`method` become node types too.

        Args:
            target: The class. Omitted when used as ``@plugin.cls(...)``.
            name: The class key; defaults to ``__name__``. It cannot contain ``.``, which separates
                it from a method's name in a method node type.
            inputs: ``{parameter: label}`` relabelling some of the constructor's input ports.
            annotations: Types for constructor parameters the signature leaves unannotated.

        Raises:
            TypeError: if the target is not a class, or an option has the wrong type.
            ValueError: if an option's value is refused, the class is already registered here, or
                the name is already declared here.
        """

        def declare(klass: type) -> type:
            where = f"plugin.cls({_describe(klass)})"
            if not isinstance(klass, type):
                raise TypeError(f"{where}: only a class can be declared with plugin.cls")
            key = _name(name, klass, where, dotted=False)
            if klass in self._class_keys:
                raise ValueError(
                    f"{where}: the class is already registered in this plugin, as "
                    f"{self._class_keys[klass]!r}"
                )
            self._claim(key, where)
            self._classes[key] = ClassDeclaration(
                klass, _inputs(inputs, where), _annotations(annotations, where)
            )
            self._class_keys[klass] = key
            return klass

        return declare if target is None else declare(target)

    def method(
        self,
        target: Callable | None = None,
        /,
        *,
        name: str | None = None,
        inputs: dict[str, str] | None = None,
        outputs: str | tuple[str, ...] | list[str] | None = None,
        annotations: dict[str, Any] | None = None,
    ):
        """Declare a method node type, of every registered class that has this function.

        The node type is ``<class key>.<name>``. A registered subclass has the method too, and so
        does an override of it in a subclass, which keeps ``name``, ``inputs`` and ``outputs`` —
        but not ``annotations``, which describe this one function's signature.

        Args:
            target: A plain function. Omitted when used as ``@plugin.method(...)``.
            name: The method's part of the node type; defaults to ``__name__``. It cannot contain
                ``.``.
            inputs: ``{parameter: label}`` relabelling some input ports.
            outputs: The output names in port order; a plain ``str`` is one name.
            annotations: Types for parameters (and ``"return"``) the signature leaves unannotated.

        Raises:
            TypeError: if the target is not a plain function — a staticmethod, classmethod,
                property or builtin — or an option has the wrong type.
            ValueError: if the target is ``__init__`` / ``__new__`` (the constructor is the class's
                own node type), it is already declared here, or an option's value is refused.
        """

        def declare(func: Callable) -> Callable:
            where = f"plugin.method({_describe(func)})"
            if not inspect.isfunction(func):
                raise TypeError(
                    f"{where}: a method node needs a plain function, not a staticmethod, "
                    f"classmethod, property or builtin"
                )
            if func.__name__ in _CONSTRUCTORS:
                raise ValueError(
                    f"{where}: the constructor is the class's own node type; declare the class "
                    f"with plugin.cls"
                )
            if func in self._marks:
                raise ValueError(f"{where}: the method is already declared in this plugin")
            self._marks[func] = _Mark(
                None if name is None else _name(name, func, where, dotted=False),
                _inputs(inputs, where),
                _outputs(outputs, where),
                _annotations(annotations, where),
            )
            return func

        return declare if target is None else declare(target)

    def functions(self) -> dict[str, Declaration]:
        """Every declared function, as ``{node type: Declaration}`` in declaration order."""
        return dict(self._functions)

    def classes(self) -> dict[str, ClassDeclaration]:
        """Every declared class, with its method node types, in declaration order.

        Resolved here rather than at the decorators, so the order of the declarations does not
        matter: a method may be declared before or after any class that has it.

        Raises:
            TypeError: if a registered class overrides a declared method with something that is
                not a function.
            ValueError: if two of one class's methods resolve to one node type, or a declared method
                belongs to no registered class.
        """
        resolved = {}
        for key, declaration in self._classes.items():
            methods: dict[str, MethodDeclaration] = {}
            for attribute in _attributes(declaration.target):
                method = self._method(declaration.target, key, attribute)
                if method is None:
                    continue
                node_type, method_declaration = method
                if node_type in methods:
                    raise ValueError(
                        f"class {key!r}: methods {methods[node_type].attribute!r} and "
                        f"{attribute!r} both declare the node type {node_type!r}"
                    )
                methods[node_type] = method_declaration
            resolved[key] = ClassDeclaration(
                declaration.target, declaration.inputs, declaration.annotations, methods
            )

        found = {
            value
            for declaration in self._classes.values()
            for owner in declaration.target.__mro__
            for value in vars(owner).values()
            if inspect.isfunction(value) and value in self._marks
        }
        stray = [func.__qualname__ for func in self._marks if func not in found]
        if stray:
            raise ValueError(
                f"methods declared with plugin.method belong to no registered class: {stray}. "
                f"Register their class with plugin.cls, and do not wrap them in staticmethod, "
                f"classmethod or property"
            )
        return resolved

    def _claim(self, node_type: str, where: str) -> None:
        """Refuse a function name or class key already declared in this plugin, of either kind."""
        if node_type in self._functions or node_type in self._classes:
            raise ValueError(f"{where}: {node_type!r} is already declared in this plugin")

    def _method(self, klass: type, key: str, attribute: str):
        """The method node type ``attribute`` gives ``klass``, or ``None`` if it gives none.

        It gives one when some class in the MRO holds a declared function under that attribute.
        The nearest such declaration supplies the labels; the function an instance actually runs
        is whatever the nearest class holding the attribute holds. When those differ, the function
        is an undeclared override: it keeps the node, with the labels but not the annotations.

        Raises:
            TypeError: if that nearest attribute is not a function.
        """
        holders = [owner for owner in klass.__mro__ if attribute in vars(owner)]
        declared = next(
            (
                vars(owner)[attribute]
                for owner in holders
                if inspect.isfunction(vars(owner)[attribute])
                and vars(owner)[attribute] in self._marks
            ),
            None,
        )
        if declared is None:
            return None

        func = vars(holders[0])[attribute]
        if not inspect.isfunction(func):
            raise TypeError(
                f"class {klass.__qualname__!r} overrides the method {attribute!r} with {func!r}, "
                f"which is not a function"
            )

        mark = self._marks[declared]
        node_type = f"{key}.{mark.name if mark.name is not None else declared.__name__}"
        annotations = mark.annotations if func is declared else {}
        return node_type, MethodDeclaration(
            attribute, Declaration(func, dict(mark.inputs), mark.outputs, dict(annotations))
        )


def _attributes(klass: type) -> list[str]:
    """Every attribute name the class or one of its bases defines, sorted.

    What ``dir()`` lists for a plain class, but read from the classes themselves: a metaclass may
    redefine ``dir()``, and would hide a declared method from it.
    """
    return sorted({name for owner in klass.__mro__ for name in vars(owner)})


def _freeze(declaration: Any, *fields: str) -> None:
    """Replace each of a frozen declaration's dict fields with a read-only view of a copy."""
    for name in fields:
        object.__setattr__(declaration, name, MappingProxyType(dict(getattr(declaration, name))))


def _describe(target: Any) -> str:
    """How an error message names a decorator's target."""
    return getattr(target, "__qualname__", None) or repr(target)


def _name(name: str | None, target: Any, where: str, *, dotted: bool) -> str:
    """The node name: ``name`` checked, or the target's ``__name__`` when it is omitted."""
    if name is None:
        name = getattr(target, "__name__", None)
        if not isinstance(name, str):
            raise TypeError(f"{where}: the target has no __name__; pass name=")
        return name
    if not isinstance(name, str):
        raise TypeError(f"{where}: name= takes a string, got {name!r}")
    if not name:
        raise ValueError(f"{where}: name= cannot be empty")
    if not dotted and "." in name:
        raise ValueError(
            f"{where}: name= cannot contain '.', which separates a class from its method in a "
            f"node type; got {name!r}"
        )
    return name


def _inputs(inputs: dict[str, str] | None, where: str) -> dict[str, str]:
    """``inputs=`` checked as far as it can be without the signature: ``{str: non-empty str}``."""
    if inputs is None:
        return {}
    if not isinstance(inputs, dict) or not all(
        isinstance(parameter, str) and isinstance(label, str) for parameter, label in inputs.items()
    ):
        raise TypeError(f"{where}: inputs= takes a dict of parameter name -> label, got {inputs!r}")
    empty = [parameter for parameter, label in inputs.items() if not label]
    if empty:
        raise ValueError(f"{where}: inputs= labels cannot be empty, for {empty}")
    return dict(inputs)


def _outputs(outputs: Any, where: str) -> tuple[str, ...] | None:
    """``outputs=`` as a tuple of names, checked as far as it can be without the signature."""
    if outputs is None:
        return None
    names = (outputs,) if isinstance(outputs, str) else outputs
    if not isinstance(names, (tuple, list)) or not all(isinstance(n, str) for n in names):
        raise TypeError(f"{where}: outputs= takes a name or a sequence of names, got {outputs!r}")
    names = tuple(names)
    if not names:
        raise ValueError(f"{where}: outputs= needs at least one name")
    if "" in names:
        raise ValueError(f"{where}: an output name cannot be empty, got {names!r}")
    repeated = sorted({n for n in names if names.count(n) > 1})
    if repeated:
        raise ValueError(f"{where}: output names must be distinct, repeated: {repeated}")
    return names


def _annotations(annotations: dict[str, Any] | None, where: str) -> dict[str, Any]:
    """``annotations=`` checked as far as it can be without the signature: a dict, ``str`` keys."""
    if annotations is None:
        return {}
    if not isinstance(annotations, dict) or not all(isinstance(k, str) for k in annotations):
        raise TypeError(
            f"{where}: annotations= takes a dict of parameter name -> type, got {annotations!r}"
        )
    return dict(annotations)
