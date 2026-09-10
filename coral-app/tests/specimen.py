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
``split_triple``              three outputs, so ``source_output`` selection has something to pick
``make_one``                  **no** inputs: a function node with ``inputs: []``
``record``                    returns ``None``: no output ports at all
``unannotated``               no annotations, which must normalise to ``Any``
``anything``                  an explicit ``Any`` on both sides
``specimen.ratio``            a dotted function name, and an **asymmetric** one
``shared_label``              a name a clash plugin also declares (duplicate-name refusal)
``Accumulator``               a class: constructor, methods, the instance at method port 0
``Gauge``                     an *unrelated* class, so a wrong instance can be rejected
``PreciseAccumulator``        a *subclass*, which must be accepted where its base is expected
============================  =================================================================

Four plugins expose it, and the split is driven entirely by what the host's merge rules need:

* :class:`SpecimenPlugin` — the whole surface above. A shape only needs to exist once.
* :class:`RivalPlugin` — a second, *non-colliding* peer. Two plugins are needed to test that the
  merge is ordered and deterministic, which is what the format golden pins.
* :class:`FunctionClashPlugin` / :class:`ClassClashPlugin` / :class:`BuiltinClashPlugin` — each
  declares one name that is already owned: a function of ``SpecimenPlugin``'s (``shared_label``), a
  class of its (``Accumulator``), and one of the *host's* builtins (``list_append``). All three must
  raise ``DuplicateNodeTypeError``. They exist only to be refused, and so are never merged with the
  others in a passing case.

Nothing here is a distribution: no entry point, no ``pyproject.toml``. The suite hands these to the
host by patching the one lookup that maps a plugin *name* to a plugin instance — see the
``specimen_plugins`` fixture in ``conftest.py``. Everything downstream of that lookup (the merge, the
port table, the registry, graph validation, execution) is production code.
"""

from typing import Any, Dict, Tuple

from coral_core import Plugin

__all__ = [
    "PLUGINS",
    "SPECIMEN",
    "RIVAL",
    "FUNCTION_CLASH",
    "CLASS_CLASH",
    "BUILTIN_CLASH",
    "SpecimenPlugin",
    "RivalPlugin",
    "FunctionClashPlugin",
    "ClassClashPlugin",
    "BuiltinClashPlugin",
    "Accumulator",
    "Gauge",
    "PreciseAccumulator",
    "Tally",
]


def add_pair(a: float, b: float) -> float:
    """Add two numbers. The plain two-in/one-out case."""
    return a + b


def to_label(value: int) -> str:
    """Render a number as a label — an edge whose type changes."""
    return f"#{value}"


def split_triple(value: float) -> Tuple[float, str, bool]:
    """Return three values, so a downstream edge must choose one with ``source_output``."""
    return value, f"{value}", value > 0.0


def make_one() -> float:
    """Take nothing, return one value: a function node with no input ports."""
    return 1.0


def record(value: float) -> None:
    """Consume a value and return nothing — a node with no outputs, so no outgoing edge is legal."""
    print(f"record: {value}")


def unannotated(value):
    """No annotations at all: the input must normalise to ``Any`` and there must be no output."""
    return value


def anything(value: Any) -> Any:
    """Explicit ``Any`` in and out — the case an edge type check must skip rather than judge."""
    return value


def ratio(numerator: float, denominator: float) -> float:
    """Registered under the dotted name ``specimen.ratio``.

    Two jobs. A dot in a node type otherwise means a class (``Accumulator.add``), so this pins that a
    dotted *function* name stays a function node. And division is **asymmetric**, which is what makes
    it possible to prove that inputs are bound by ``target_input`` rather than by the order the edges
    happen to appear in — with ``add_pair`` or a multiplication, a swap would be invisible.
    """
    return numerator / denominator


def shared_label(value: float) -> str:
    """A name :class:`FunctionClashPlugin` also declares, so the two cannot be selected together."""
    return f"specimen:{value}"


def rival_only(value: float) -> float:
    """:class:`RivalPlugin`'s own function: a second plugin's contribution, colliding with nothing."""
    return -value


class Accumulator:
    """A class with methods, plus members that must **not** become node types."""

    class_attribute = 42

    def __init__(self, start: float):
        self.start = start

    def add(self, amount: float) -> float:
        """The instance arrives at port 0; ``amount`` is port 1."""
        return self.start + amount

    def total(self) -> float:
        """A method taking nothing but the instance: exactly one input port."""
        return self.start

    def _hidden(self, value: int) -> int:
        """Underscore-prefixed, so it is not a node type."""
        return value


class Gauge:
    """A class unrelated to :class:`Accumulator`, for the wrong-instance case."""

    def __init__(self, reading: float):
        self.reading = reading

    def label(self) -> str:
        return f"gauge:{self.reading}"


class PreciseAccumulator(Accumulator):
    """A subclass of :class:`Accumulator`, which must be accepted wherever its base is expected."""

    def __init__(self, start: float, digits: int):
        super().__init__(start)
        self.digits = digits

    def rounded(self) -> float:
        return round(self.start, self.digits)


class Tally:
    """:class:`RivalPlugin`'s own class, so the second plugin contributes a constructor too."""

    def __init__(self, count: int):
        self.count = count

    def bump(self) -> int:
        return self.count + 1


class SpecimenPlugin(Plugin):
    """The whole designed surface, as one plugin."""

    def get_functions(self) -> Dict[str, Any]:
        return {
            "add_pair": add_pair,
            "to_label": to_label,
            "split_triple": split_triple,
            "make_one": make_one,
            "record": record,
            "unannotated": unannotated,
            "anything": anything,
            "specimen.ratio": ratio,
            "shared_label": shared_label,
        }

    def get_classes(self) -> Dict[str, Any]:
        return {
            "Accumulator": Accumulator,
            "Gauge": Gauge,
            "PreciseAccumulator": PreciseAccumulator,
        }


class RivalPlugin(Plugin):
    """A second peer, colliding with nothing: the host's merge must be ordered and deterministic."""

    def get_functions(self) -> Dict[str, Any]:
        return {"rival_only": rival_only}

    def get_classes(self) -> Dict[str, Any]:
        return {"Tally": Tally}


class FunctionClashPlugin(Plugin):
    """Declares a *function* name :class:`SpecimenPlugin` already owns; selecting both is refused."""

    def get_functions(self) -> Dict[str, Any]:
        return {"shared_label": lambda value: "clash"}

    def get_classes(self) -> Dict[str, Any]:
        return {}


class ClassClashPlugin(Plugin):
    """Declares a *class* name :class:`SpecimenPlugin` already owns; selecting both is refused.

    A class name is a node type too — a constructor plus one ``Class.method`` per method — so the
    same rule holds there, and it is checked separately because ``build_class_map`` is a separate
    merge.
    """

    def get_functions(self) -> Dict[str, Any]:
        return {}

    def get_classes(self) -> Dict[str, Any]:
        return {"Accumulator": Tally}


class BuiltinClashPlugin(Plugin):
    """Declares one of the host's builtin names; selecting it is refused.

    Not a peer's name but the *host's*, and the outcome is deliberately the same. #25 let a builtin
    win silently here; that made the same mistake behave two different ways depending on who else
    owned the name, and left a plugin author with no signal at all.
    """

    def get_functions(self) -> Dict[str, Any]:
        return {"list_append": lambda lst, item: "clash"}

    def get_classes(self) -> Dict[str, Any]:
        return {}


#: The name each specimen plugin is selected by. Any string would do: these are keys into the
#: lookup the ``specimen_plugins`` fixture patches in, not entry-point names, and no distribution
#: declares them. They are deliberately unlike any real plugin's name.
SPECIMEN = "specimen"
RIVAL = "rival"
FUNCTION_CLASH = "function-clash"
CLASS_CLASH = "class-clash"
BUILTIN_CLASH = "builtin-clash"

#: Every specimen plugin, by the name it is selected under.
PLUGINS = {
    SPECIMEN: SpecimenPlugin,
    RIVAL: RivalPlugin,
    FUNCTION_CLASH: FunctionClashPlugin,
    CLASS_CLASH: ClassClashPlugin,
    BUILTIN_CLASH: BuiltinClashPlugin,
}
