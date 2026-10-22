"""The designed plugin surface the host's own tests run against.

The host describes, validates and executes *any* callable a plugin hands it — that is its whole job.
So its tests must not be written against a particular plugin's functions: doing so ties the host
suite to a plugin being installed (that is where ~38 ``@pytest.mark.<plugin>`` markers came from) and
leaves the shapes under test to whatever that plugin happens to declare, rather than to what the host
must handle.

This module is that surface, designed. Every entry exists because some host behaviour needs it:

============================  =================================================================
entry                         the shape it exists for
============================  =================================================================
``add_pair``                  two typed inputs, one output — the workhorse
``to_label``                  a type change across an edge (int -> str)
``split_triple``              three outputs, so ``source_output`` selection has something to pick;
                              named with ``outputs=``
``pair``                      a bare ``tuple`` return: **one** output port, passed on whole
``short_triple``              declares three outputs, returns two — an annotation that lies
``not_a_tuple``               declares two outputs, returns no tuple at all
``push``                      writes a parameter (``writes=``): a pass-through after the return
``make_one``                  **no** inputs: a function node with ``inputs: []``
``record``                    returns ``None``: no output ports at all
``unannotated``               no annotations, which must normalise to ``Any``
``anything``                  an explicit ``Any`` on both sides
``specimen.ratio``            a dotted function name, and an **asymmetric** one
``shared_label``              a name a clash plugin also declares (duplicate-name refusal)
``Accumulator``               a class: constructor, methods, the instance at method port 0; ``add``
                              names its output with ``outputs=``, which ``PreciseAccumulator``
                              inherits; ``deposit`` is the one method that is not ``const``
``Gauge``                     an *unrelated* class, so a wrong instance can be rejected
``PreciseAccumulator``        a *subclass*, which must be accepted where its base is expected
``Resettable``                a second parent for ``Ledger``, unrelated to ``Accumulator``
``Ledger``                    a subclass of both: a chain and a second parent at once
``Meter``                     an *abstract* class, detected by ``inspect.isabstract``: a socket type
                              with no constructor node; ``read`` is declared on it
``Thermometer``               a concrete ``Meter``, overriding ``read`` and declaring it ``const``
============================  =================================================================

Seven plugins expose it, and the split is driven entirely by what the host's merge rules need:

* :data:`specimen_plugin` — the whole surface above. A shape only needs to exist once.
* :data:`rival_plugin` — a second, *non-colliding* peer. Two plugins are needed to test that the
  merge is ordered and deterministic, which is what the format golden pins.
* :data:`function_clash_plugin` / :data:`class_clash_plugin` / :data:`builtin_clash_plugin` — each
  declares one name that is already owned: a function of ``specimen_plugin``'s (``shared_label``),
  a class of its (``Accumulator``), and one of the *host's* builtins (``list_append``). All three
  must raise ``DuplicateNodeTypeError``. They exist only to be refused, and so are never merged with
  the others in a passing case.
* :data:`collection_clash_plugin` — declares a class keyed ``list``, which collides with the
  primitive ``list``. It must raise ``DuplicateNodeTypeError`` too.
* :data:`hierarchy_clash_plugin` — registers ``Audited``, a subclass of ``Accumulator``. Plugins do
  not share a class hierarchy, so selecting it with :data:`specimen_plugin` must raise
  ``ValueError``.

Nothing here is a distribution: no entry point, no ``pyproject.toml``. The suite hands these to the
host by patching the one lookup that maps a plugin *name* to a plugin instance — see the
``specimen_plugins`` fixture in ``conftest.py``. Everything downstream of that lookup (the merge, the
port table, the registry, graph validation, execution) is production code.
"""

from abc import ABC, abstractmethod
from typing import Any, Tuple

from coral_core import Plugin

__all__ = [
    "PLUGINS",
    "SPECIMEN",
    "RIVAL",
    "FUNCTION_CLASH",
    "CLASS_CLASH",
    "BUILTIN_CLASH",
    "COLLECTION_CLASH",
    "HIERARCHY_CLASH",
    "specimen_plugin",
    "rival_plugin",
    "function_clash_plugin",
    "class_clash_plugin",
    "builtin_clash_plugin",
    "collection_clash_plugin",
    "hierarchy_clash_plugin",
    "Accumulator",
    "Gauge",
    "PreciseAccumulator",
    "Resettable",
    "Ledger",
    "Meter",
    "Thermometer",
    "Tally",
    "Audited",
]

#: The whole designed surface, as one plugin.
specimen_plugin = Plugin()

#: A second peer, colliding with nothing: the host's merge must be ordered and deterministic.
rival_plugin = Plugin()

#: Declares a *function* name :data:`specimen_plugin` already owns; selecting both is refused.
function_clash_plugin = Plugin()

#: Declares a *class* name :data:`specimen_plugin` already owns; selecting both is refused.
class_clash_plugin = Plugin()

#: Declares one of the host's builtin names; selecting it is refused.
builtin_clash_plugin = Plugin()

#: Declares a class keyed ``list``, the name of a primitive; selecting it is refused.
collection_clash_plugin = Plugin()

#: Registers a subclass of a class :data:`specimen_plugin` registers; selecting both is refused.
hierarchy_clash_plugin = Plugin()


@specimen_plugin.function
def add_pair(a: float, b: float) -> float:
    """Add two numbers. The plain two-in/one-out case."""
    return a + b


@specimen_plugin.function
def to_label(value: int) -> str:
    """Render a number as a label — an edge whose type changes."""
    return f"#{value}"


@specimen_plugin.function(outputs=("value", "text", "positive"))
def split_triple(value: float) -> Tuple[float, str, bool]:
    """Return three values, so a downstream edge must choose one with ``source_output``."""
    return value, f"{value}", value > 0.0


@specimen_plugin.function
def make_one() -> float:
    """Take nothing, return one value: a function node with no input ports."""
    return 1.0


@specimen_plugin.function
def record(value: float) -> None:
    """Consume a value and return nothing — a node with no outputs, so no outgoing edge is legal."""
    print(f"record: {value}")


@specimen_plugin.function
def unannotated(value):
    """No annotations at all: the input must normalise to ``Any`` and there must be no output."""
    return value


@specimen_plugin.function
def anything(value: Any) -> Any:
    """Explicit ``Any`` in and out — the case an edge type check must skip rather than judge."""
    return value


@specimen_plugin.function(name="specimen.ratio")
def ratio(numerator: float, denominator: float) -> float:
    """Registered under the dotted name ``specimen.ratio``.

    Two jobs. A dot in a node type otherwise means a class (``Accumulator.add``), so this pins that a
    dotted *function* name stays a function node. And division is **asymmetric**, which is what makes
    it possible to prove that inputs are bound by ``target_input`` rather than by the order the edges
    happen to appear in — with ``add_pair`` or a multiplication, a swap would be invisible.
    """
    return numerator / denominator


@specimen_plugin.function
def shared_label(value: float) -> str:
    """A name :data:`function_clash_plugin` also declares, so the two cannot be selected together."""
    return f"specimen:{value}"


@specimen_plugin.function
def pair() -> tuple:
    """Return a tuple from a node with **one** output port.

    ``tuple`` is a single annotation, so this node has one output and its value is passed on whole.
    Deciding that from the value instead — ``isinstance(result, tuple)`` — would index into it and
    deliver ``10`` where ``(10, 20)`` is what the node produced.
    """
    return 10, 20


@specimen_plugin.function
def short_triple() -> Tuple[Any, Any, Any]:
    """Declare three outputs and return two: an annotation that lies about its own arity."""
    return 1, 2


@specimen_plugin.function
def not_a_tuple() -> Tuple[Any, Any]:
    """Declare two outputs and return something that is not a tuple at all."""
    return 7


@specimen_plugin.function(writes="items")
def push(items: list, item: Any) -> int:
    """Append to ``items`` in place and return its new length: ``items`` is a pass-through, the
    output after the return value, so its registry entry lists outputs out of ascending order."""
    items.append(item)
    return len(items)


@rival_plugin.function
def rival_only(value: float) -> float:
    """:data:`rival_plugin`'s own function: a second plugin's contribution, colliding with nothing."""
    return -value


@specimen_plugin.cls
class Accumulator:
    """A class with methods, plus members that must **not** become node types."""

    class_attribute = 42

    def __init__(self, start: float):
        self.start = start

    @specimen_plugin.method(outputs="total", const=True)
    def add(self, amount: float) -> float:
        """The instance arrives at port 0; ``amount`` is port 1."""
        return self.start + amount

    @specimen_plugin.method(const=True)
    def total(self) -> float:
        """A method taking nothing but the instance: exactly one input port."""
        return self.start

    @specimen_plugin.method
    def deposit(self, amount: float) -> float:
        """Not ``const``: it modifies the instance, so the instance is a pass-through, output 0,
        ahead of the return value."""
        self.start += amount
        return self.start

    def _hidden(self, value: int) -> int:
        """Not declared, so it is not a node type."""
        return value


@specimen_plugin.cls
class Gauge:
    """A class unrelated to :class:`Accumulator`, for the wrong-instance case."""

    def __init__(self, reading: float):
        self.reading = reading

    @specimen_plugin.method(const=True)
    def label(self) -> str:
        return f"gauge:{self.reading}"


@specimen_plugin.cls
class PreciseAccumulator(Accumulator):
    """A subclass of :class:`Accumulator`, which must be accepted wherever its base is expected."""

    def __init__(self, start: float, digits: int):
        super().__init__(start)
        self.digits = digits

    @specimen_plugin.method(const=True)
    def rounded(self) -> float:
        return round(self.start, self.digits)


@specimen_plugin.cls
class Resettable:
    """A second parent for :class:`Ledger`, unrelated to :class:`Accumulator`."""

    def __init__(self, level: float):
        self.level = level

    @specimen_plugin.method(const=True)
    def reset(self) -> float:
        """Return a constant: on a :class:`Ledger` this class's ``__init__`` never runs."""
        return 0.0


@specimen_plugin.cls
class Ledger(PreciseAccumulator, Resettable):
    """A chain and a second parent at once, MRO ``Ledger, PreciseAccumulator, Accumulator,
    Resettable``: it must be accepted wherever any of them is expected."""


@specimen_plugin.cls
class Meter(ABC):
    """An abstract class, detected rather than declared: ``read`` is abstract, so Python cannot
    instantiate it. Its key types sockets; it has no constructor node."""

    @specimen_plugin.method(const=True)
    @abstractmethod
    def read(self) -> float:
        """Declared here, implemented by every concrete subclass."""


@specimen_plugin.cls
class Thermometer(Meter):
    """A concrete :class:`Meter`, overriding ``read``: declared again, as an override of a
    ``const`` method must be."""

    def __init__(self, celsius: float):
        self.celsius = celsius

    @specimen_plugin.method(const=True)
    def read(self) -> float:
        return self.celsius


@rival_plugin.cls
class Tally:
    """:data:`rival_plugin`'s own class, so the second plugin contributes a constructor too."""

    def __init__(self, count: int):
        self.count = count

    @rival_plugin.method(const=True)
    def bump(self) -> int:
        return self.count + 1


# A class name is a node type too — a constructor plus its methods — so the duplicate rule holds
# there as well, and it is checked separately because `build_class_map` is a separate merge.
function_clash_plugin.function(lambda value: "clash", name="shared_label")
class_clash_plugin.cls(Tally, name="Accumulator")

# Not a peer's name but the *host's*, and the outcome is deliberately the same: letting a builtin
# win silently made the same mistake behave two different ways depending on who else owned the
# name, and left a plugin author with no signal at all.
builtin_clash_plugin.function(lambda lst, item: "clash", name="list_append")

collection_clash_plugin.cls(Tally, name="list")


class Audited(Accumulator):
    """A subclass of :data:`specimen_plugin`'s :class:`Accumulator`, registered by another plugin:
    plugins do not share a class hierarchy."""


hierarchy_clash_plugin.cls(Audited)

#: The name each specimen plugin is selected by. Any string would do: these are keys into the
#: lookup the ``specimen_plugins`` fixture patches in, not entry-point names, and no distribution
#: declares them. They are deliberately unlike any real plugin's name.
SPECIMEN = "specimen"
RIVAL = "rival"
FUNCTION_CLASH = "function-clash"
CLASS_CLASH = "class-clash"
BUILTIN_CLASH = "builtin-clash"
COLLECTION_CLASH = "collection-clash"
HIERARCHY_CLASH = "hierarchy-clash"

#: Every specimen plugin, by the name it is selected under.
PLUGINS = {
    SPECIMEN: specimen_plugin,
    RIVAL: rival_plugin,
    FUNCTION_CLASH: function_clash_plugin,
    CLASS_CLASH: class_clash_plugin,
    BUILTIN_CLASH: builtin_clash_plugin,
    COLLECTION_CLASH: collection_clash_plugin,
    HIERARCHY_CLASH: hierarchy_clash_plugin,
}
