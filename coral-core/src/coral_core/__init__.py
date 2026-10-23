"""coral-core — the shared contract for the coral plugin system.

A plugin is an instance of :class:`Plugin`. A function, a class or a method becomes a node type by
being declared on it with one of three decorators, which also carry every option about that node::

    plugin = Plugin()

    @plugin.function
    def add(a: float, b: float) -> float: ...

    @plugin.cls
    class Calculator:
        def __init__(self, initial_value: float): ...

        @plugin.method(const=True, outputs="value")
        def get_value(self) -> float: ...

A class other classes derive from, but which is never built itself, is declared abstract:
``plugin.cls(Base, abstract=True)``, or implicitly when Python cannot instantiate it
(``inspect.isabstract``). Its key still types sockets; it has no constructor node.

A method is taken to modify its instance unless declared ``const=True``; a function or method
modifies none of its other parameters unless it names them with ``writes=``. A modified input is a
pass-through: an output too, so the host can order every node reading the value before the one
modifying it. An override may promise more than what it overrides, never less.

A callable that cannot be decorated where it is defined — a builtin, a class from another library —
is declared with the same decorators used as a plain call: ``plugin.function(math.atan2, ...)``.

The options are kept in the plugin, never on the decorated object: a builtin has no ``__dict__`` to
write to, and an option stored on a function two plugins both declare would let one overwrite the
other. What the host receives are declarations — :class:`Declaration`, :class:`ClassDeclaration` —
each a callable together with what its decorator said. Reading a signature and building ports from
it is the host's job, not this package's; this package reads one only to compare an override's
written parameters with its base's, by position.

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

# Stands for a decorator's omitted target, as in `@plugin.function(...)`. Not `None`: a target
# that is `None` is a mistake to refuse, such as a failed `getattr(module, "name", None)`.
_OMITTED: Any = object()


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
        writes: The parameters the callable modifies in place, in the order given. Each is a
            pass-through: its input port is an output too. The others are read. A method's
            instance is never among them: see :attr:`MethodDeclaration.const`.
    """

    target: Callable
    inputs: Mapping[str, str] = field(default_factory=dict)
    outputs: tuple[str, ...] | None = None
    annotations: Mapping[str, Any] = field(default_factory=dict)
    writes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _freeze(self, "inputs", "annotations")


@dataclass(frozen=True)
class MethodDeclaration:
    """One method node type of a class.

    Attributes:
        attribute: The attribute the method is defined under. A method node runs the function the
            declaration of its instance's class resolves under it, so an override in a registered
            subclass is what runs.
        declaration: The function the class holds under that attribute, with its labels.
        const: Whether the method leaves its instance unmodified. A method that is not ``const``
            passes its instance through, as its first output.
    """

    attribute: str
    declaration: Declaration
    const: bool = False


@dataclass(frozen=True)
class ClassDeclaration:
    """A registered class: its constructor node type, unless it is abstract, and its method node
    types.

    The constructor is the class's own node type, so the class carries the constructor's options
    itself. It has no ``outputs``: a constructor's single output is the instance, which carries no
    name.

    Attributes:
        target: The class.
        inputs: ``{parameter: label}`` for the constructor's input ports.
        annotations: Types for the constructor's parameters that its signature leaves unannotated.
        methods: ``{method node name: MethodDeclaration}``, keyed by the full node name
            (``"Calculator.get_value"``), sorted by attribute name.
        abstract: Whether the class only types sockets. An abstract class has no constructor
            node, so ``inputs`` and ``annotations`` are empty; its declared methods are still node
            types.
    """

    target: type
    inputs: Mapping[str, str] = field(default_factory=dict)
    annotations: Mapping[str, Any] = field(default_factory=dict)
    methods: Mapping[str, MethodDeclaration] = field(default_factory=dict)
    abstract: bool = False

    def __post_init__(self) -> None:
        _freeze(self, "inputs", "annotations", "methods")


@dataclass(frozen=True)
class _Mark:
    """What ``Plugin.method`` was told about one function, before any class is known."""

    name: str
    inputs: dict[str, str]
    outputs: tuple[str, ...] | None
    annotations: dict[str, Any]
    writes: tuple[str, ...]
    const: bool


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
        target: Callable = _OMITTED,
        /,
        *,
        name: str | None = None,
        inputs: dict[str, str] | None = None,
        outputs: str | tuple[str, ...] | list[str] | None = None,
        annotations: dict[str, Any] | None = None,
        writes: str | tuple[str, ...] | list[str] | None = None,
    ):
        """Declare a function node type.

        Args:
            target: Any callable that is not a class. Omitted when used as ``@plugin.function(...)``.
            name: The node type; defaults to the callable's ``__name__``. May contain ``.``, as in
                ``math.sqrt``.
            inputs: ``{parameter: label}`` relabelling some input ports.
            outputs: The output names in port order; a plain ``str`` is one name.
            annotations: Types for parameters (and ``"return"``) the signature leaves unannotated.
            writes: The parameters the function modifies in place; a plain ``str`` is one name.
                Each is a pass-through, an output after the return values.

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
                _writes(writes, where),
            )
            return func

        return declare if target is _OMITTED else declare(target)

    def cls(
        self,
        target: type = _OMITTED,
        /,
        *,
        name: str | None = None,
        inputs: dict[str, str] | None = None,
        annotations: dict[str, Any] | None = None,
        abstract: bool | None = None,
    ):
        """Declare a class: its key becomes a socket type and, unless the class is abstract, its
        constructor a node type, keyed by the class's name.

        Only the methods declared with :meth:`method` become node types too, abstract class or not.
        There is no ``writes=``: a constructor modifies none of its inputs.

        Args:
            target: The class. Omitted when used as ``@plugin.cls(...)``.
            name: The class key; defaults to ``__name__``. It cannot contain ``.``, which separates
                it from a method's name in a method node type.
            inputs: ``{parameter: label}`` relabelling some of the constructor's input ports.
            annotations: Types for constructor parameters the signature leaves unannotated.
            abstract: Whether the class only types sockets, with no constructor node. Omitted, it
                is ``inspect.isabstract(target)``: a class Python cannot instantiate offers no
                constructor.

        Raises:
            TypeError: if the target is not a class, or is a ``typing.Protocol``, or an option has
                the wrong type.
            ValueError: if an option's value is refused, the class is already registered here, or
                the name is already declared here; if ``abstract=False`` is given for a class with
                unimplemented abstract methods, or ``inputs=`` / ``annotations=`` for an abstract
                class.
        """

        def declare(klass: type) -> type:
            where = f"plugin.cls({_describe(klass)})"
            if not isinstance(klass, type):
                raise TypeError(f"{where}: only a class can be declared with plugin.cls")
            # `typing.is_protocol` reads this flag, from Python 3.13 on. A class inheriting a
            # protocol by name has it False: only the protocol itself is structural.
            if getattr(klass, "_is_protocol", False):
                raise TypeError(
                    f"{where}: the class is a typing.Protocol, whose subclasses are decided by "
                    f"structure, while a registered class's bases are decided by inheritance; "
                    f"register a base class the classes inherit instead"
                )
            key = _name(name, klass, where, dotted=False)
            if klass in self._class_keys:
                raise ValueError(
                    f"{where}: the class is already registered in this plugin, as "
                    f"{self._class_keys[klass]!r}"
                )
            self._claim(key, where)
            class_inputs = _inputs(inputs, where)
            class_annotations = _annotations(annotations, where)
            is_abstract = _abstract(abstract, klass, where)
            if is_abstract and (class_inputs or class_annotations):
                raise ValueError(
                    f"{where}: the class is abstract, so it has no constructor node whose "
                    f"parameters inputs= or annotations= could describe"
                )
            self._classes[key] = ClassDeclaration(
                klass, class_inputs, class_annotations, abstract=is_abstract
            )
            self._class_keys[klass] = key
            return klass

        return declare if target is _OMITTED else declare(target)

    def method(
        self,
        target: Callable = _OMITTED,
        /,
        *,
        name: str | None = None,
        inputs: dict[str, str] | None = None,
        outputs: str | tuple[str, ...] | list[str] | None = None,
        annotations: dict[str, Any] | None = None,
        writes: str | tuple[str, ...] | list[str] | None = None,
        const: bool = False,
    ):
        """Declare a method node type, of every registered class that has this function.

        The node type is ``<class key>.<name>``. A registered subclass has the method too, and so
        does an override of it in a subclass, which keeps ``name``, ``inputs``, ``outputs``,
        ``writes`` and ``const`` — but not ``annotations``, which describe this one function's
        signature. An override may promise more than what it overrides, never less: it may be
        ``const`` where its base is not, and modify fewer parameters, compared by position. An
        override of a ``const`` method must therefore be declared itself, with ``const=True``.

        Args:
            target: A plain function. Omitted when used as ``@plugin.method(...)``.
            name: The method's part of the node type; defaults to ``__name__``. It cannot contain
                ``.``.
            inputs: ``{parameter: label}`` relabelling some input ports.
            outputs: The output names in port order; a plain ``str`` is one name.
            annotations: Types for parameters (and ``"return"``) the signature leaves unannotated.
            writes: The parameters other than the instance that the method modifies in place; a
                plain ``str`` is one name. Each is a pass-through, an output after the return
                values.
            const: Whether the method leaves its instance unmodified. If not, the default, the
                instance is a pass-through, the method's first output.

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
            if not isinstance(const, bool):
                raise TypeError(f"{where}: const= takes a bool, got {const!r}")
            self._marks[func] = _Mark(
                _name(name, func, where, dotted=False),
                _inputs(inputs, where),
                _outputs(outputs, where),
                _annotations(annotations, where),
                _writes(writes, where),
                const,
            )
            return func

        return declare if target is _OMITTED else declare(target)

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
                belongs to no registered class, or an undeclared override replaces a method
                declared with ``annotations=``, or an override promises less than a method it
                overrides, or a class holds a declared method as its constructor.
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
                declaration.target,
                declaration.inputs,
                declaration.annotations,
                methods,
                abstract=declaration.abstract,
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
        is an undeclared override: it keeps the node and the labels. It cannot keep
        ``annotations=``, which describe the declared function's signature, so a declaration with
        ``annotations=`` refuses an undeclared override. Nor may it promise less than what it
        overrides: see :meth:`_check_override`.

        Raises:
            TypeError: if that nearest attribute is not a function.
            ValueError: if it is an undeclared override of a declaration with ``annotations=``, or
                the attribute is the constructor, or it promises less than a declared function it
                overrides.
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

        if attribute in _CONSTRUCTORS:
            raise ValueError(
                f"class {key!r} holds the declared method {declared.__qualname__!r} as its "
                f"constructor {attribute!r}; the constructor is the class's own node type, so it "
                f"cannot be a method"
            )

        holder = holders[0]
        overrider = (
            f"class {key!r}"
            if holder is klass
            else f"class {key!r}: its base {self._class_keys.get(holder, holder.__qualname__)!r}"
        )
        func = vars(holder)[attribute]
        if not inspect.isfunction(func):
            raise TypeError(
                f"{overrider} overrides the method {attribute!r} with {func!r}, which is not a "
                f"function"
            )

        mark = self._marks[declared]
        if func is not declared and mark.annotations:
            raise ValueError(
                f"{overrider} overrides the method {attribute!r}, whose "
                f"declaration types {list(mark.annotations)} with annotations=; annotations "
                f"describe one function, so declare the override itself with plugin.method"
            )
        self._check_override(overrider, attribute, func, declared, holders)
        node_type = f"{key}.{mark.name}"
        return node_type, MethodDeclaration(
            attribute,
            Declaration(func, mark.inputs, mark.outputs, mark.annotations, mark.writes),
            mark.const,
        )

    def _check_override(
        self, overrider: str, attribute: str, func: Callable, declared: Callable, holders: list
    ) -> None:
        """Refuse ``func`` if it promises less than a declared function it overrides.

        ``func`` is what runs, and it keeps the ``const=`` and ``writes=`` of ``declared``, the
        nearest declared function: its own when it is declared. That promise is compared with every
        other declared function under ``attribute`` in the MRO, not only the nearest: a method node
        of any of those classes, given an instance of this one, runs ``func`` behind that class's
        ports. Written parameters are compared by position, since an override may rename them; an
        undeclared override's inherited names are resolved on its own signature, as the host
        resolves them, and must all be there.

        Raises:
            ValueError: if one of them is ``const`` and ``func`` is not declared ``const=True``, or
                ``func`` modifies a parameter one of them reads, or lacks a parameter its
                ``writes=`` names, or takes another number of parameters than one of them.
        """
        mark = self._marks[declared]
        bases = [
            vars(owner)[attribute]
            for owner in holders
            if inspect.isfunction(vars(owner)[attribute])
            and vars(owner)[attribute] in self._marks
            and vars(owner)[attribute] is not func
        ]
        # An undeclared override has its declaration among them, so without one nothing is compared.
        if not bases:
            return
        # Resolved on the function that runs, as the host resolves them: an undeclared override
        # inherits the names, not the positions. A declared function's own writes= naming no
        # parameter is the host's to report, as it reports inputs=.
        parameters = list(inspect.signature(func).parameters)
        missing = [name for name in mark.writes if name not in parameters]
        if missing and func is not declared:
            raise ValueError(
                f"{overrider} overrides the method {attribute!r}, whose declaration writes "
                f"{missing} with writes=, with a function that has no such parameter; declare the "
                f"override itself with plugin.method"
            )
        written = _positions(parameters, mark.writes)
        for base in bases:
            base_mark = self._marks[base]
            base_parameters = list(inspect.signature(base).parameters)
            # A method node of a base passes the override as many arguments as the base takes.
            if len(parameters) != len(base_parameters):
                raise ValueError(
                    f"{overrider} overrides the method {attribute!r} with {func.__qualname__!r}, "
                    f"which takes {len(parameters)} parameter(s), where {base.__qualname__!r} "
                    f"takes {len(base_parameters)}; a method node of the base passes it that many "
                    f"arguments"
                )
            if base_mark.const and func is not declared:
                raise ValueError(
                    f"{overrider} overrides the method {attribute!r}, which {base.__qualname__!r} "
                    f"declares const=True; an undeclared override is not const, so declare the "
                    f"override itself with plugin.method(const=True)"
                )
            if base_mark.const and not mark.const:
                raise ValueError(
                    f"{overrider} overrides the method {attribute!r}, which {base.__qualname__!r} "
                    f"declares const=True, with {func.__qualname__!r}, declared without "
                    f"const=True; an override may promise more than its base, never less"
                )
            if not written:
                continue
            read = sorted(written - _positions(base_parameters, base_mark.writes))
            read = [parameters[i] for i in read]
            if read:
                raise ValueError(
                    f"{overrider} overrides the method {attribute!r} with one that modifies "
                    f"{read}, which {base.__qualname__!r} reads, compared by position; an "
                    f"override may promise more than its base, never less"
                )


def _attributes(klass: type) -> list[str]:
    """Every attribute name the class or one of its bases defines, sorted.

    What ``dir()`` lists for a plain class, but read from the classes themselves: a metaclass may
    redefine ``dir()``, and would hide a declared method from it.
    """
    return sorted({name for owner in klass.__mro__ for name in vars(owner)})


def _positions(parameters: list[str], names: tuple[str, ...]) -> set[int]:
    """The positions of ``names`` among a function's ``parameters``. A name that is not a
    parameter is skipped: the host checks ``writes=`` against the signature."""
    return {parameters.index(name) for name in names if name in parameters}


def _freeze(declaration: Any, *fields: str) -> None:
    """Replace each of a frozen declaration's dict fields with a read-only view of a copy."""
    for name in fields:
        object.__setattr__(declaration, name, MappingProxyType(dict(getattr(declaration, name))))


def _describe(target: Any) -> str:
    """How an error message names a decorator's target."""
    return getattr(target, "__qualname__", None) or repr(target)


def _name(name: str | None, target: Any, where: str, *, dotted: bool) -> str:
    """The node name: ``name``, or the target's ``__name__`` when omitted; checked either way."""
    if name is None:
        name = getattr(target, "__name__", None)
        if not isinstance(name, str):
            raise TypeError(f"{where}: the target has no __name__; pass name=")
        source, hint = "its __name__", "; pass name="
    elif not isinstance(name, str):
        raise TypeError(f"{where}: name= takes a string, got {name!r}")
    else:
        source, hint = "name=", ""
    if not name:
        raise ValueError(f"{where}: {source} cannot be empty{hint}")
    if not dotted and "." in name:
        raise ValueError(
            f"{where}: {source} cannot contain '.', which separates a class from its method in a "
            f"node type; got {name!r}{hint}"
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


def _writes(writes: Any, where: str) -> tuple[str, ...]:
    """``writes=`` as a tuple of parameter names, checked as far as it can be without the
    signature."""
    if writes is None:
        return ()
    names = (writes,) if isinstance(writes, str) else writes
    if not isinstance(names, (tuple, list)) or not all(isinstance(n, str) for n in names):
        raise TypeError(
            f"{where}: writes= takes a parameter name or a sequence of them, got {writes!r}"
        )
    names = tuple(names)
    if "" in names:
        raise ValueError(f"{where}: a parameter name in writes= cannot be empty, got {names!r}")
    repeated = sorted({n for n in names if names.count(n) > 1})
    if repeated:
        raise ValueError(f"{where}: writes= names each parameter once, repeated: {repeated}")
    return names


def _annotations(annotations: dict[str, Any] | None, where: str) -> dict[str, Any]:
    """``annotations=`` checked as far as it can be without the signature: a dict, ``str`` keys,
    and values that are not ``str`` — a type's name is never resolved, so it would type nothing."""
    if annotations is None:
        return {}
    if not isinstance(annotations, dict) or not all(isinstance(k, str) for k in annotations):
        raise TypeError(
            f"{where}: annotations= takes a dict of parameter name -> type, got {annotations!r}"
        )
    named = [key for key, value in annotations.items() if isinstance(value, str)]
    if named:
        raise TypeError(
            f"{where}: annotations= takes types, not their names: {named} given as strings, "
            f"which are never resolved. For a class defined later, use the call form once it "
            f"exists: plugin.method(Cls.m, annotations={{'x': Cls}})"
        )
    return dict(annotations)


def _abstract(abstract: bool | None, klass: type, where: str) -> bool:
    """Whether a class is abstract: ``abstract=`` when given, else ``inspect.isabstract``.

    ``abstract=False`` cannot make a class with unimplemented abstract methods concrete: Python
    refuses to instantiate it, so its constructor node would fail every time it ran."""
    if abstract is None:
        return inspect.isabstract(klass)
    if not isinstance(abstract, bool):
        raise TypeError(f"{where}: abstract= takes a bool, got {abstract!r}")
    if not abstract and inspect.isabstract(klass):
        raise ValueError(
            f"{where}: abstract=False, but the class has unimplemented abstract methods "
            f"{sorted(klass.__abstractmethods__)}; Python cannot instantiate it, so it has no "
            f"constructor node. Omit abstract= or implement them"
        )
    return abstract
