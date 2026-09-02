"""Tests for the port table (stage 2) — ``coral_app.nodeports``.

Everything here runs on hand-written maps rather than on installed plugins: the port table's job is
to describe *any* callable, so the tests need no plugin and are never skipped. Whether the real
plugins are described correctly is proven by the golden registry files.
"""

import inspect
from typing import Any, Tuple

import pytest
from coral_app.nodeports import (
    CONSTRUCTOR,
    FUNCTION,
    METHOD,
    PRIMITIVE,
    build_port_table,
    methods_of,
)


def annotated(a: int, b: str) -> float:
    """A function with a full set of annotations."""
    return 0.0


def returns_nothing(x: float) -> None:
    """A function that declares no return value."""


def returns_triple(x: float) -> Tuple[float, str, bool]:
    """A function returning three values."""
    return x, "", False


def unannotated(x):
    """A function with neither parameter nor return annotation."""
    return x


class Widget:
    """A class with one public method and assorted things that must not be registered."""

    class_attribute = 42

    def __init__(self, size: float, label: str = "w"):
        self.size = size
        self.label = label

    def resize(self, factor: float) -> float:
        return self.size * factor

    def describe(self) -> str:
        return self.label

    def _private(self, x: int) -> int:
        return x

    @staticmethod
    def helper(x: int) -> int:
        return x


PRIMITIVES = {"int": int, "float": float, "str": str, "any": Any}


class TestTableCoverage:
    """One entry per node type, keyed as a graph's ``type`` field."""

    def test_one_entry_per_node_type(self):
        """GIVEN a function map, a class map and a primitives map
        WHEN the port table is built
        THEN it holds exactly one entry per primitive, function, constructor and method."""
        table = build_port_table(
            function_map={"annotated": annotated, "returns_nothing": returns_nothing},
            class_map={"Widget": Widget},
            primitives=PRIMITIVES,
        )

        assert set(table) == {
            "int",
            "float",
            "str",
            "any",
            "annotated",
            "returns_nothing",
            "Widget",
            "Widget.describe",
            "Widget.helper",
            "Widget.resize",
        }

    def test_kinds_are_assigned_per_node_type(self):
        """GIVEN a table covering all four node types
        WHEN each entry's kind is read
        THEN it names the node type it was derived from."""
        table = build_port_table(
            function_map={"annotated": annotated},
            class_map={"Widget": Widget},
            primitives=PRIMITIVES,
        )

        assert table["int"].kind == PRIMITIVE
        assert table["annotated"].kind == FUNCTION
        assert table["Widget"].kind == CONSTRUCTOR
        assert table["Widget.resize"].kind == METHOD

    def test_empty_maps_give_an_empty_table(self):
        """GIVEN no maps at all
        WHEN the port table is built
        THEN it is empty rather than an error."""
        assert build_port_table() == {}


class TestInputs:
    """Input ports: name and annotation, in port order."""

    def test_function_inputs_follow_the_signature(self):
        """GIVEN an annotated function
        WHEN its ports are read
        THEN its inputs are its parameters, in declaration order, with their annotations."""
        table = build_port_table(function_map={"annotated": annotated})

        assert table["annotated"].inputs == [("a", int), ("b", str)]

    def test_constructor_inputs_omit_self(self):
        """GIVEN a class
        WHEN its constructor ports are read
        THEN the inputs are the ``__init__`` parameters without ``self``."""
        table = build_port_table(class_map={"Widget": Widget})

        assert table["Widget"].inputs == [("size", float), ("label", str)]

    def test_method_input_zero_is_the_instance(self):
        """GIVEN a class method
        WHEN its ports are read
        THEN port 0 is ``self``, annotated with the class, and the parameters follow."""
        table = build_port_table(class_map={"Widget": Widget})

        assert table["Widget.resize"].inputs == [("self", Widget), ("factor", float)]

    def test_method_with_no_parameters_has_only_the_instance(self):
        """GIVEN a method taking nothing but ``self``
        WHEN its ports are read
        THEN it has exactly one input, the instance."""
        table = build_port_table(class_map={"Widget": Widget})

        assert table["Widget.describe"].inputs == [("self", Widget)]

    def test_primitive_has_no_inputs(self):
        """GIVEN a primitive type
        WHEN its ports are read
        THEN it has no inputs."""
        table = build_port_table(primitives=PRIMITIVES)

        assert table["float"].inputs == []

    def test_missing_annotation_becomes_any(self):
        """GIVEN a parameter with no annotation
        WHEN its port is read
        THEN the annotation is ``Any``, not ``Signature.empty``."""
        table = build_port_table(function_map={"unannotated": unannotated})

        assert table["unannotated"].inputs == [("x", Any)]
        assert table["unannotated"].inputs[0][1] is not inspect.Signature.empty


class TestOutputs:
    """Output ports, numbered 0-based within outputs."""

    def test_single_return_gives_one_output(self):
        """GIVEN a function returning one value
        WHEN its ports are read
        THEN it has a single output carrying the return annotation."""
        table = build_port_table(function_map={"annotated": annotated})

        assert table["annotated"].outputs == [float]

    def test_tuple_return_gives_one_output_per_element(self):
        """GIVEN a function annotated ``Tuple[float, str, bool]``
        WHEN its ports are read
        THEN it has three outputs, one per element, in order."""
        table = build_port_table(function_map={"returns_triple": returns_triple})

        assert table["returns_triple"].outputs == [float, str, bool]

    def test_none_return_gives_no_outputs(self):
        """GIVEN a function annotated ``-> None``
        WHEN its ports are read
        THEN it has no outputs — there is nothing to pass on."""
        table = build_port_table(function_map={"returns_nothing": returns_nothing})

        assert table["returns_nothing"].outputs == []

    def test_missing_return_annotation_gives_no_outputs(self):
        """GIVEN a function with no return annotation
        WHEN its ports are read
        THEN it has no outputs, exactly as an explicit ``-> None`` does."""
        table = build_port_table(function_map={"unannotated": unannotated})

        assert table["unannotated"].outputs == []

    def test_constructor_outputs_the_instance(self):
        """GIVEN a class
        WHEN its constructor ports are read
        THEN it has one output, annotated with the class itself."""
        table = build_port_table(class_map={"Widget": Widget})

        assert table["Widget"].outputs == [Widget]

    def test_primitive_outputs_its_own_type(self):
        """GIVEN a primitive type
        WHEN its ports are read
        THEN it has one output, annotated with that type."""
        table = build_port_table(primitives=PRIMITIVES)

        assert table["int"].outputs == [int]
        assert table["any"].outputs == [Any]


class TestMethodEnumeration:
    """Which members of a class become method nodes."""

    def test_underscore_names_are_skipped(self):
        """GIVEN a class with a private method and dunder methods
        WHEN the table is built
        THEN no underscore-prefixed name becomes a node type."""
        table = build_port_table(class_map={"Widget": Widget})

        assert "Widget._private" not in table
        assert not any("._" in node_type for node_type in table)

    def test_non_callable_attributes_are_skipped(self):
        """GIVEN a class carrying a plain (non-callable) class attribute
        WHEN the table is built
        THEN it does not become a node type."""
        table = build_port_table(class_map={"Widget": Widget})

        assert "Widget.class_attribute" not in table

    def test_staticmethods_are_registered_as_methods(self):
        """GIVEN a class with a staticmethod
        WHEN the table is built
        THEN it registers as a method node with an instance at port 0.

        Not a design choice: ``getattr(cls, name)`` on a staticmethod yields the plain function, so
        the ``inspect.isfunction`` filter admits it. Pinned here as long-standing behaviour that no
        installed plugin exercises (none has a staticmethod)."""
        table = build_port_table(class_map={"Widget": Widget})

        assert table["Widget.helper"].kind == METHOD
        assert table["Widget.helper"].inputs == [("self", Widget), ("x", int)]

    def test_c_extension_class_registers_a_constructor_and_no_methods(self):
        """GIVEN a C extension class, whose methods are not ``inspect.isfunction``
        WHEN the table is built
        THEN it contributes a constructor entry only — ``signature(cls)`` refusing on such a type
             must not abort the table."""
        import datetime

        table = build_port_table(class_map={"date": datetime.date})

        assert table["date"].kind == CONSTRUCTOR
        assert methods_of(table, "date") == []

    def test_methods_of_lists_one_class(self):
        """GIVEN a table built from two classes
        WHEN one class's methods are requested
        THEN only that class's fully qualified method keys come back."""
        table = build_port_table(class_map={"Widget": Widget, "Other": Widget})

        assert methods_of(table, "Widget") == [
            "Widget.describe",
            "Widget.helper",
            "Widget.resize",
        ]


class TestPrecedence:
    """Key collisions resolve the way the executor's old ``_classify`` did."""

    def test_a_dotted_function_name_wins_over_a_method(self):
        """GIVEN a function named ``Widget.resize`` alongside the class ``Widget``
        WHEN the table is built
        THEN the function keeps the key — function beats method, as before."""
        table = build_port_table(
            function_map={"Widget.resize": annotated},
            class_map={"Widget": Widget},
        )

        assert table["Widget.resize"].kind == FUNCTION
        assert table["Widget.resize"].inputs == [("a", int), ("b", str)]


def returns_bare_tuple(x: float) -> tuple:
    """A function whose single output happens to carry a tuple."""
    return (x, x)


def returns_bare_Tuple(x: float) -> Tuple:
    """A function whose tuple return declares no elements."""
    return (x, x)


def returns_empty_Tuple(x: float) -> Tuple[()]:
    """A function whose tuple return declares an empty element list."""
    return ()


def returns_variadic_Tuple(x: float) -> Tuple[Any, ...]:
    """A function whose tuple return is variadic, so it has no static arity."""
    return (x, x)


class TestTupleReturnAnnotations:
    """A tuple return must declare its elements.

    The port table's output arity is the claim every consumer trusts — the registry's ports, graph
    checks 7 and 8, and the executor's indexing. A tuple spelling that cannot state an arity is
    rejected where the claim is made, rather than mis-described and failing somewhere downstream.
    """

    def test_declared_elements_are_one_port_each(self):
        """GIVEN a function returning ``Tuple[float, str, bool]``
        WHEN the table is built
        THEN it has one output port per declared element."""
        table = build_port_table(function_map={"returns_triple": returns_triple})

        assert table["returns_triple"].outputs == [float, str, bool]

    def test_plain_tuple_is_a_single_output(self):
        """GIVEN a function annotated with plain ``tuple`` rather than ``Tuple[...]``
        WHEN the table is built
        THEN it has exactly one output port, annotated ``tuple``.

        This is the case output-port resolution hinges on: one output that happens to carry a
        tuple, which the executor must pass on whole instead of indexing into."""
        table = build_port_table(function_map={"pair": returns_bare_tuple})

        assert table["pair"].outputs == [tuple]

    @pytest.mark.parametrize(
        "func",
        [returns_bare_Tuple, returns_empty_Tuple, returns_variadic_Tuple],
        ids=["Tuple", "Tuple[()]", "Tuple[Any, ...]"],
    )
    def test_a_tuple_without_declared_elements_is_rejected(self, func):
        """GIVEN a function whose tuple return declares no usable element list
        WHEN the table is built
        THEN it raises ValueError naming the node type, rather than silently producing the wrong
        number of ports."""
        with pytest.raises(ValueError, match="does not declare its output ports"):
            build_port_table(function_map={"offender": func})

    def test_the_message_names_the_offending_node_type(self):
        """GIVEN a badly annotated function registered under a given node type
        WHEN the table is built
        THEN the error names that node type, so the author knows which function to fix."""
        with pytest.raises(ValueError, match="'offender'"):
            build_port_table(function_map={"offender": returns_bare_Tuple})

    def test_a_method_is_rejected_the_same_way(self):
        """GIVEN a class whose public method returns a bare ``Tuple``
        WHEN the table is built
        THEN it raises, naming the ``Class.method`` node type — the check is not function-only."""

        class Broken:
            def compute(self) -> Tuple:
                return ()

        with pytest.raises(ValueError, match="'Broken.compute'"):
            build_port_table(class_map={"Broken": Broken})
