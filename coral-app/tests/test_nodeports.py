"""Tests for the port table (stage 2) — ``coral_app.nodeports``.

Everything here runs on hand-written declarations rather than on installed plugins: the port
table's job is to describe *any* callable, so the tests need no plugin and are never skipped.
Whether the real plugins are described correctly is proven by the golden registry files.

Which methods a class declares, and with which labels, is ``coral_core``'s business and tested
there; here a declaration is taken as given, and what is tested is the ports read from it.
"""

import datetime
import inspect
from typing import Any, Tuple

import pytest
from coral_app import PRIMITIVES_MAP
from coral_app.errors import DuplicateNodeTypeError
from coral_app.nodeports import (
    CONSTRUCTOR,
    FUNCTION,
    METHOD,
    PRIMITIVE,
    Port,
    build_port_table,
    methods_of,
)
from coral_core import Plugin
from host_suite import declared_classes, declared_functions


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


class Widget:
    """A class with two declared methods (:data:`WIDGET_METHODS`) and members that are not."""

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


#: The methods of :class:`Widget` declared wherever it is.
WIDGET_METHODS = (Widget.resize, Widget.describe)

PRIMITIVES = {"int": int, "float": float, "str": str, "any": Any}


class TestTableCoverage:
    """One entry per node type, keyed as a graph's ``type`` field."""

    def test_one_entry_per_node_type(self):
        """GIVEN a function map, a class map and a primitives map
        WHEN the port table is built
        THEN it holds exactly one entry per primitive, function, constructor and method."""
        table = build_port_table(
            function_map=declared_functions(
                {"annotated": annotated, "returns_nothing": returns_nothing}
            ),
            class_map=declared_classes({"Widget": Widget}, WIDGET_METHODS),
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
            "Widget.resize",
        }

    def test_kinds_are_assigned_per_node_type(self):
        """GIVEN a table covering all four node types
        WHEN each entry's kind is read
        THEN it names the node type it was derived from."""
        table = build_port_table(
            function_map=declared_functions({"annotated": annotated}),
            class_map=declared_classes({"Widget": Widget}, WIDGET_METHODS),
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
        table = build_port_table(function_map=declared_functions({"annotated": annotated}))

        assert table["annotated"].inputs == [Port("a", int), Port("b", str)]

    def test_constructor_inputs_omit_self(self):
        """GIVEN a class
        WHEN its constructor ports are read
        THEN the inputs are the ``__init__`` parameters without ``self``."""
        table = build_port_table(class_map=declared_classes({"Widget": Widget}, WIDGET_METHODS))

        assert table["Widget"].inputs == [Port("size", float), Port("label", str)]

    def test_method_input_zero_is_the_instance(self):
        """GIVEN a class method
        WHEN its ports are read
        THEN port 0 is ``self``, annotated with the class and marked as the instance, and the
             parameters follow."""
        table = build_port_table(class_map=declared_classes({"Widget": Widget}, WIDGET_METHODS))

        assert table["Widget.resize"].inputs == [
            Port("self", Widget, instance=True),
            Port("factor", float),
        ]

    def test_method_with_no_parameters_has_only_the_instance(self):
        """GIVEN a method taking nothing but ``self``
        WHEN its ports are read
        THEN it has exactly one input, the instance."""
        table = build_port_table(class_map=declared_classes({"Widget": Widget}, WIDGET_METHODS))

        assert table["Widget.describe"].inputs == [Port("self", Widget, instance=True)]

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
        table = build_port_table(function_map=declared_functions({"unannotated": unannotated}))

        assert table["unannotated"].inputs == [Port("x", Any)]
        assert table["unannotated"].inputs[0].annotation is not inspect.Signature.empty


class TestOutputs:
    """Output ports, numbered 0-based within outputs."""

    def test_single_return_gives_one_output(self):
        """GIVEN a function returning one value
        WHEN its ports are read
        THEN it has a single output carrying the return annotation."""
        table = build_port_table(function_map=declared_functions({"annotated": annotated}))

        assert table["annotated"].outputs == [Port("", float)]

    def test_tuple_return_gives_one_output_per_element(self):
        """GIVEN a function annotated ``Tuple[float, str, bool]``
        WHEN its ports are read
        THEN it has three outputs, one per element, in order."""
        table = build_port_table(
            function_map=declared_functions({"returns_triple": returns_triple})
        )

        assert table["returns_triple"].outputs == [Port("", float), Port("", str), Port("", bool)]

    def test_none_return_gives_no_outputs(self):
        """GIVEN a function annotated ``-> None``
        WHEN its ports are read
        THEN it has no outputs — there is nothing to pass on."""
        table = build_port_table(
            function_map=declared_functions({"returns_nothing": returns_nothing})
        )

        assert table["returns_nothing"].outputs == []

    def test_missing_return_annotation_gives_no_outputs(self):
        """GIVEN a function with no return annotation
        WHEN its ports are read
        THEN it has no outputs, exactly as an explicit ``-> None`` does."""
        table = build_port_table(function_map=declared_functions({"unannotated": unannotated}))

        assert table["unannotated"].outputs == []

    def test_constructor_outputs_the_instance(self):
        """GIVEN a class
        WHEN its constructor ports are read
        THEN it has one output, annotated with the class itself."""
        table = build_port_table(class_map=declared_classes({"Widget": Widget}, WIDGET_METHODS))

        assert table["Widget"].outputs == [Port("", Widget)]

    def test_primitive_outputs_its_own_type(self):
        """GIVEN a primitive type
        WHEN its ports are read
        THEN it has one output, annotated with that type."""
        table = build_port_table(primitives=PRIMITIVES)

        assert table["int"].outputs == [Port("", int)]
        assert table["any"].outputs == [Port("", Any)]


class TestMethodEnumeration:
    """Which method nodes a class contributes: the ones its declaration lists."""

    def test_only_declared_methods_are_entries(self):
        """GIVEN Widget declared with two of its methods
        WHEN the table is built
        THEN those two are its method entries; its private method, staticmethod and plain
        attribute are not."""
        table = build_port_table(class_map=declared_classes({"Widget": Widget}, WIDGET_METHODS))

        assert methods_of(table, "Widget") == ["Widget.describe", "Widget.resize"]

    def test_a_renamed_method_keeps_its_attribute(self):
        """GIVEN a method declared under a name other than its attribute
        WHEN the table is built
        THEN its entry is keyed by the declared name and records the attribute, which is what the
        executor looks up on the instance."""
        plugin = Plugin()

        @plugin.cls
        class Counter:
            @plugin.method(name="current")
            def get(self) -> int:
                return 0

        table = build_port_table(class_map=plugin.classes())

        assert table["Counter.current"].attribute == "get"
        assert "Counter.get" not in table

    def test_only_a_method_has_an_attribute(self):
        """GIVEN a function and a class
        WHEN the table is built
        THEN only the method entries carry an attribute."""
        table = build_port_table(
            function_map=declared_functions({"annotated": annotated}),
            class_map=declared_classes({"Widget": Widget}, WIDGET_METHODS),
        )

        assert table["annotated"].attribute is None
        assert table["Widget"].attribute is None
        assert table["Widget.resize"].attribute == "resize"

    def test_a_c_extension_class_is_refused(self):
        """GIVEN a C extension class from which no signature can be read
        WHEN the table is built
        THEN ValueError naming the node type: without a signature there are no ports to read."""
        with pytest.raises(ValueError, match="'date'"):
            build_port_table(class_map=declared_classes({"date": datetime.date}))

    def test_methods_of_lists_one_class(self):
        """GIVEN a table built from two classes
        WHEN one class's methods are requested
        THEN only that class's fully qualified method keys come back."""

        class Other:
            def resize(self, factor: float) -> float:
                return factor

        table = build_port_table(
            class_map=declared_classes(
                {"Widget": Widget, "Other": Other}, [*WIDGET_METHODS, Other.resize]
            )
        )

        assert methods_of(table, "Widget") == ["Widget.describe", "Widget.resize"]


class TestDeclaredNameClashIsRefused:
    """One name declared as two different *kinds* of node is refused, not silently resolved.

    A graph names only the node type, so whichever entry won would decide what the graph computes
    while the JSON looks identical — the same argument that makes a duplicate function name a
    ``DuplicateNodeTypeError`` in stage 1. Stage 1 cannot see these: it merges the function and class
    surfaces into two separate maps, and this is the only place all three surfaces meet.
    """

    def test_a_function_and_a_class_sharing_a_name_raise(self):
        """GIVEN one name declared as both a function and a class
        WHEN the table is built
        THEN DuplicateNodeTypeError is raised, rather than the function silently winning."""
        with pytest.raises(DuplicateNodeTypeError):
            build_port_table(
                function_map=declared_functions({"Widget": annotated}),
                class_map=declared_classes({"Widget": Widget}, WIDGET_METHODS),
            )

    def test_a_dotted_function_named_after_a_declared_method_raises(self):
        """GIVEN a function named ``Widget.resize`` alongside the class ``Widget`` declaring ``resize``
        WHEN the table is built
        THEN DuplicateNodeTypeError names both kinds, rather than the function silently hiding the
        method."""
        with pytest.raises(DuplicateNodeTypeError) as raised:
            build_port_table(
                function_map=declared_functions({"Widget.resize": annotated}),
                class_map=declared_classes({"Widget": Widget}, WIDGET_METHODS),
            )

        message = str(raised.value)
        assert "Widget.resize" in message
        assert FUNCTION in message and METHOD in message

    def test_a_function_named_after_a_primitive_raises(self):
        """GIVEN a function named ``int``
        WHEN the table is built alongside the primitives
        THEN DuplicateNodeTypeError is raised — a primitive is a node type too."""
        with pytest.raises(DuplicateNodeTypeError):
            build_port_table(
                function_map=declared_functions({"int": annotated}), primitives=PRIMITIVES
            )

    def test_a_class_named_after_a_primitive_raises(self):
        """GIVEN a class keyed ``float``
        WHEN the table is built alongside the primitives
        THEN DuplicateNodeTypeError is raised."""
        with pytest.raises(DuplicateNodeTypeError):
            build_port_table(class_map=declared_classes({"float": Widget}), primitives=PRIMITIVES)

    def test_the_message_names_the_node_type_and_both_kinds(self):
        """GIVEN a function and a class both named ``Widget``
        WHEN the table is built
        THEN the message names the node type and the two kinds that claimed it."""
        with pytest.raises(DuplicateNodeTypeError) as raised:
            build_port_table(
                function_map=declared_functions({"Widget": annotated}),
                class_map=declared_classes({"Widget": Widget}, WIDGET_METHODS),
            )

        message = str(raised.value)
        assert "Widget" in message
        assert FUNCTION in message and CONSTRUCTOR in message


class TestCollectionNamesCollideWithPrimitives:
    """``list``, ``set`` and ``dict`` are primitive node types, so a bare name claiming one collides."""

    def test_a_class_named_after_a_collection_raises(self):
        """GIVEN a class keyed ``list``, alongside the primitives
        WHEN the table is built
        THEN DuplicateNodeTypeError is raised, naming the primitive it collides with."""
        with pytest.raises(DuplicateNodeTypeError, match="primitive"):
            build_port_table(
                class_map=declared_classes({"list": Widget}), primitives=PRIMITIVES_MAP
            )

    def test_a_function_named_after_a_collection_raises(self):
        """GIVEN a function keyed ``dict``, alongside the primitives
        WHEN the table is built
        THEN DuplicateNodeTypeError is raised, naming the primitive it collides with."""
        with pytest.raises(DuplicateNodeTypeError, match="primitive"):
            build_port_table(
                function_map=declared_functions({"dict": annotated}), primitives=PRIMITIVES_MAP
            )

    def test_a_method_named_after_a_collection_is_accepted(self):
        """GIVEN a class with a declared method named ``list``
        WHEN the table is built
        THEN ``Shelf.list`` is a method entry: its key carries the class, so it never meets the
        primitive ``list``."""

        class Shelf:
            def list(self) -> str:
                return ""

        table = build_port_table(
            class_map=declared_classes({"Shelf": Shelf}, [Shelf.list]), primitives=PRIMITIVES_MAP
        )

        assert table["Shelf.list"].kind == METHOD


class TestAClassHasOneKey:
    """A class is named by its key, so one registered under two keys is refused."""

    def test_a_class_under_two_keys_raises(self):
        """GIVEN one class registered under the keys ``First`` and ``Second``, by two plugins
        WHEN the table is built
        THEN DuplicateNodeTypeError is raised, and the message names both keys."""
        with pytest.raises(DuplicateNodeTypeError) as raised:
            build_port_table(
                class_map={
                    **declared_classes({"First": Widget}),
                    **declared_classes({"Second": Widget}),
                }
            )

        message = str(raised.value)
        assert "'First'" in message and "'Second'" in message


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
        table = build_port_table(
            function_map=declared_functions({"returns_triple": returns_triple})
        )

        assert table["returns_triple"].outputs == [Port("", float), Port("", str), Port("", bool)]

    def test_plain_tuple_is_a_single_output(self):
        """GIVEN a function annotated with plain ``tuple`` rather than ``Tuple[...]``
        WHEN the table is built
        THEN it has exactly one output port, annotated ``tuple``.

        This is the case output-port resolution hinges on: one output that happens to carry a
        tuple, which the executor must pass on whole instead of indexing into."""
        table = build_port_table(function_map=declared_functions({"pair": returns_bare_tuple}))

        assert table["pair"].outputs == [Port("", tuple)]

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
            build_port_table(function_map=declared_functions({"offender": func}))

    def test_the_message_names_the_offending_node_type(self):
        """GIVEN a badly annotated function registered under a given node type
        WHEN the table is built
        THEN the error names that node type, so the author knows which function to fix."""
        with pytest.raises(ValueError, match="'offender'"):
            build_port_table(function_map=declared_functions({"offender": returns_bare_Tuple}))

    def test_a_method_is_rejected_the_same_way(self):
        """GIVEN a class whose declared method returns a bare ``Tuple``
        WHEN the table is built
        THEN it raises, naming the ``Class.method`` node type — the check is not function-only."""

        class Broken:
            def compute(self) -> Tuple:
                return ()

        with pytest.raises(ValueError, match="'Broken.compute'"):
            build_port_table(class_map=declared_classes({"Broken": Broken}, [Broken.compute]))


class TestOutputNames:
    """``outputs=`` names a callable's outputs; the annotation alone decides how many there are.

    The decorator checks the names on their own when it is applied. Whether there is one name per
    output depends on the return annotation, which only the port table reads — so that check lives
    here.
    """

    def test_a_function_s_names_reach_its_outputs(self):
        """GIVEN a function returning three values, declared with three names
        WHEN the table is built
        THEN each output port carries its name, in order, next to its annotation."""
        plugin = Plugin()

        @plugin.function(outputs=("value", "text", "flag"))
        def triple(x: float) -> Tuple[float, str, bool]:
            return x, "", False

        table = build_port_table(function_map=plugin.functions())

        assert table["triple"].outputs == [
            Port("value", float),
            Port("text", str),
            Port("flag", bool),
        ]

    def test_a_method_s_name_reaches_its_output(self):
        """GIVEN a method declared with one name
        WHEN the table is built
        THEN its single output port carries it."""
        plugin = Plugin()

        @plugin.cls
        class Meter:
            @plugin.method(outputs="reading")
            def read(self) -> float:
                return 0.0

        table = build_port_table(class_map=plugin.classes())

        assert table["Meter.read"].outputs == [Port("reading", float)]

    def test_an_inherited_method_keeps_its_base_s_names(self):
        """GIVEN a subclass inheriting a method declared with a name
        WHEN the table is built
        THEN the subclass's entry carries the same name."""
        plugin = Plugin()

        @plugin.cls
        class Meter:
            @plugin.method(outputs="reading")
            def read(self) -> float:
                return 0.0

        @plugin.cls
        class FineMeter(Meter):
            pass

        table = build_port_table(class_map=plugin.classes())

        assert table["FineMeter.read"].outputs == [Port("reading", float)]

    def test_an_undeclared_callable_s_outputs_are_unnamed(self):
        """GIVEN a function returning three values, declared without outputs=
        WHEN the table is built
        THEN every output's name is "" — no placeholder is invented."""
        table = build_port_table(
            function_map=declared_functions({"returns_triple": returns_triple})
        )

        assert [port.name for port in table["returns_triple"].outputs] == ["", "", ""]

    def test_too_few_names_are_refused(self):
        """GIVEN a function returning three values, declared with two names
        WHEN the table is built
        THEN ValueError names the node type."""
        plugin = Plugin()
        plugin.function(returns_triple, name="offender", outputs=("value", "text"))

        with pytest.raises(ValueError, match="'offender'"):
            build_port_table(function_map=plugin.functions())

    def test_too_many_names_are_refused(self):
        """GIVEN a function returning one value, declared with two names
        WHEN the table is built
        THEN ValueError gives both counts."""
        plugin = Plugin()
        plugin.function(annotated, outputs=("value", "text"))

        with pytest.raises(ValueError, match=r"names 2 outputs.*declares 1"):
            build_port_table(function_map=plugin.functions())

    def test_names_on_a_callable_returning_nothing_are_refused(self):
        """GIVEN a function annotated ``-> None``, declared with a name
        WHEN the table is built
        THEN ValueError: there is no output to carry the name."""
        plugin = Plugin()
        plugin.function(returns_nothing, outputs="result")

        with pytest.raises(ValueError, match="declares 0"):
            build_port_table(function_map=plugin.functions())


def keyword_only(a: int, *, b: int) -> int:
    """A function with a keyword-only parameter."""
    return a + b


def variadic(*args: int) -> int:
    """A function taking ``*args``."""
    return sum(args)


def keywords(**kwargs: int) -> int:
    """A function taking ``**kwargs``."""
    return len(kwargs)


class TestSignatures:
    """Every port is passed by position, so the signature must have one parameter per port."""

    @pytest.mark.parametrize(
        "func",
        [keyword_only, variadic, keywords],
        ids=["keyword-only", "*args", "**kwargs"],
    )
    def test_a_non_positional_parameter_is_refused(self, func):
        """GIVEN a function with a keyword-only, *args or **kwargs parameter
        WHEN the table is built
        THEN ValueError naming the node type: no edge could ever feed that parameter."""
        with pytest.raises(ValueError, match=r"'offender'.*cannot be passed by position"):
            build_port_table(function_map=declared_functions({"offender": func}))

    def test_a_positional_only_parameter_is_accepted(self):
        """GIVEN a function with a positional-only parameter, as builtins have
        WHEN the table is built
        THEN it is an input port like any other."""

        def f(a: int, /, b: int) -> int:
            return a + b

        table = build_port_table(function_map=declared_functions({"f": f}))

        assert table["f"].inputs == [Port("a", int), Port("b", int)]

    def test_a_constructor_with_a_keyword_only_parameter_is_refused(self):
        """GIVEN a class whose constructor has a keyword-only parameter
        WHEN the table is built
        THEN ValueError naming the class: the class cannot be a node type at all."""

        class Strict:
            def __init__(self, *, size: float):
                self.size = size

        with pytest.raises(ValueError, match=r"'Strict'.*\['size'\]"):
            build_port_table(class_map=declared_classes({"Strict": Strict}))

    def test_a_callable_without_a_signature_is_refused(self):
        """GIVEN a builtin from which no signature can be read
        WHEN the table is built
        THEN ValueError naming the node type, chained to the reason."""
        with pytest.raises(ValueError, match="'max'") as raised:
            build_port_table(function_map=declared_functions({"max": max}))

        assert raised.value.__cause__ is not None

    def test_a_method_s_first_parameter_is_its_instance_whatever_its_name(self):
        """GIVEN a declared method whose first parameter is not called ``self``
        WHEN the table is built
        THEN that parameter is port 0, the instance, and is not an input of its own."""
        plugin = Plugin()

        @plugin.cls
        class Meter:
            @plugin.method
            def scaled(this, factor: float) -> float:
                return factor

        table = build_port_table(class_map=plugin.classes())

        assert table["Meter.scaled"].inputs == [
            Port("self", Meter, instance=True),
            Port("factor", float),
        ]

    def test_a_method_without_parameters_is_refused(self):
        """GIVEN a declared method taking no parameter at all
        WHEN the table is built
        THEN ValueError naming the node type: nothing could receive the instance."""
        plugin = Plugin()

        @plugin.cls
        class Meter:
            @plugin.method
            def broken() -> float:
                return 0.0

        with pytest.raises(ValueError, match=r"'Meter.broken'.*instance"):
            build_port_table(class_map=plugin.classes())


class TestAnnotations:
    """``annotations=`` fills the types a signature leaves out, and nothing else."""

    def test_a_missing_parameter_type_is_filled(self):
        """GIVEN an unannotated parameter, declared with annotations=
        WHEN the table is built
        THEN its port carries the declared type."""
        plugin = Plugin()
        plugin.function(unannotated, annotations={"x": float})

        table = build_port_table(function_map=plugin.functions())

        assert table["unannotated"].inputs == [Port("x", float)]

    def test_a_missing_return_type_is_filled(self):
        """GIVEN a callable with no return annotation, declared with annotations={"return": ...}
        WHEN the table is built
        THEN it has the declared output — the annotation is what decides there is one."""
        plugin = Plugin()
        plugin.function(unannotated, annotations={"x": float, "return": float})

        table = build_port_table(function_map=plugin.functions())

        assert table["unannotated"].outputs == [Port("", float)]

    def test_a_constructor_parameter_is_filled(self):
        """GIVEN a class whose constructor parameter is unannotated, declared with annotations=
        WHEN the table is built
        THEN the constructor's port carries the declared type."""

        class Box:
            def __init__(self, size):
                self.size = size

        plugin = Plugin()
        plugin.cls(Box, annotations={"size": float})

        table = build_port_table(class_map=plugin.classes())

        assert table["Box"].inputs == [Port("size", float)]

    def test_a_method_parameter_is_filled(self):
        """GIVEN a method whose parameter is unannotated, declared with annotations=
        WHEN the table is built
        THEN the parameter's port, after the instance, carries the declared type."""
        plugin = Plugin()

        @plugin.cls
        class Meter:
            @plugin.method(annotations={"scale": float})
            def read(self, scale) -> float:
                return scale

        table = build_port_table(class_map=plugin.classes())

        assert table["Meter.read"].inputs == [
            Port("self", Meter, instance=True),
            Port("scale", float),
        ]

    @pytest.mark.parametrize("key", ["a", "return"])
    def test_an_annotated_slot_is_refused(self, key):
        """GIVEN a parameter or return the code already annotates
        WHEN annotations= types it again
        THEN ValueError: a declared type must never contradict the code."""
        plugin = Plugin()
        plugin.function(annotated, annotations={key: float})

        with pytest.raises(ValueError, match="already annotates"):
            build_port_table(function_map=plugin.functions())

    def test_an_explicit_any_counts_as_annotated(self):
        """GIVEN a parameter annotated ``Any``
        WHEN annotations= types it
        THEN ValueError: ``Any`` is a declared type, not a missing one."""

        def loose(x: Any) -> Any:
            return x

        plugin = Plugin()
        plugin.function(loose, annotations={"x": float})

        with pytest.raises(ValueError, match="already annotates"):
            build_port_table(function_map=plugin.functions())

    def test_a_key_naming_no_parameter_is_refused(self):
        """GIVEN annotations= naming a parameter the callable does not have
        WHEN the table is built
        THEN ValueError listing the parameters it does have."""
        plugin = Plugin()
        plugin.function(unannotated, annotations={"y": float})

        with pytest.raises(ValueError, match=r"'y'.*\['x'\]"):
            build_port_table(function_map=plugin.functions())

    def test_self_is_refused_on_a_method(self):
        """GIVEN a method declared with annotations= naming ``self``
        WHEN the table is built
        THEN ValueError: port 0 is the instance, typed by its class."""
        plugin = Plugin()

        @plugin.cls
        class Meter:
            @plugin.method(annotations={"self": int})
            def read(self) -> float:
                return 0.0

        with pytest.raises(ValueError, match="instance"):
            build_port_table(class_map=plugin.classes())

    def test_a_differently_named_instance_is_refused_too(self):
        """GIVEN a method whose first parameter is ``this``, declared with annotations= naming it
        WHEN the table is built
        THEN ValueError: it is port 0, the instance, whatever its name."""
        plugin = Plugin()

        @plugin.cls
        class Meter:
            @plugin.method(annotations={"this": int})
            def read(this) -> float:
                return 0.0

        with pytest.raises(ValueError, match="instance"):
            build_port_table(class_map=plugin.classes())

    def test_return_is_refused_on_a_constructor(self):
        """GIVEN a class declared with annotations={"return": ...}
        WHEN the table is built
        THEN ValueError: a constructor's output is the instance."""

        class Box:
            def __init__(self, size: float):
                self.size = size

        plugin = Plugin()
        plugin.cls(Box, annotations={"return": int})

        with pytest.raises(ValueError, match="constructor"):
            build_port_table(class_map=plugin.classes())

    @pytest.mark.parametrize("option", ["inputs", "annotations"])
    def test_self_is_not_a_constructor_parameter(self, option):
        """GIVEN a class declared with inputs= or annotations= naming ``self``
        WHEN the table is built
        THEN ValueError naming it: a constructor's ports are its parameters after the instance."""

        class Box:
            def __init__(self, size: float):
                self.size = size

        plugin = Plugin()
        plugin.cls(Box, **{option: {"self": "box" if option == "inputs" else float}})

        with pytest.raises(ValueError, match="'self'"):
            build_port_table(class_map=plugin.classes())


class TestInputLabels:
    """``inputs=`` relabels input ports; the editor tells ports apart by their labels."""

    def test_a_labelled_port_takes_the_label(self):
        """GIVEN a function declared with inputs= relabelling one parameter
        WHEN the table is built
        THEN that port carries the label, and the others keep their parameter's name."""
        plugin = Plugin()
        plugin.function(annotated, inputs={"b": "text"})

        table = build_port_table(function_map=plugin.functions())

        assert table["annotated"].inputs == [Port("a", int), Port("text", str)]

    def test_a_key_naming_no_parameter_is_refused(self):
        """GIVEN inputs= naming a parameter the callable does not have
        WHEN the table is built
        THEN ValueError naming it."""
        plugin = Plugin()
        plugin.function(annotated, inputs={"c": "third"})

        with pytest.raises(ValueError, match="'c'"):
            build_port_table(function_map=plugin.functions())

    def test_self_is_refused_on_a_method(self):
        """GIVEN a method declared with inputs= naming ``self``
        WHEN the table is built
        THEN ValueError: port 0 is the instance."""
        plugin = Plugin()

        @plugin.cls
        class Meter:
            @plugin.method(inputs={"self": "meter"})
            def read(self) -> float:
                return 0.0

        with pytest.raises(ValueError, match="instance"):
            build_port_table(class_map=plugin.classes())

    def test_two_ports_with_one_label_are_refused(self):
        """GIVEN a label equal to another parameter's name
        WHEN the table is built
        THEN ValueError: the two ports could not be told apart."""
        plugin = Plugin()
        plugin.function(annotated, inputs={"b": "a"})

        with pytest.raises(ValueError, match="distinct"):
            build_port_table(function_map=plugin.functions())

    def test_a_method_label_cannot_be_self(self):
        """GIVEN a method parameter relabelled ``self``
        WHEN the table is built
        THEN ValueError: port 0 is already called that."""
        plugin = Plugin()

        @plugin.cls
        class Meter:
            @plugin.method(inputs={"scale": "self"})
            def read(self, scale: float) -> float:
                return scale

        with pytest.raises(ValueError, match="distinct"):
            build_port_table(class_map=plugin.classes())

    def test_a_parameter_can_be_both_relabelled_and_typed(self):
        """GIVEN an unannotated parameter declared with both inputs= and annotations=
        WHEN the table is built
        THEN its port carries the label and the declared type."""
        plugin = Plugin()
        plugin.function(unannotated, inputs={"x": "value"}, annotations={"x": float})

        table = build_port_table(function_map=plugin.functions())

        assert table["unannotated"].inputs == [Port("value", float)]

    def test_annotations_are_keyed_by_parameter_not_by_label(self):
        """GIVEN a parameter relabelled with inputs=, and annotations= keyed by the label
        WHEN the table is built
        THEN ValueError naming the label: annotations= names parameters, and a label is not one."""
        plugin = Plugin()
        plugin.function(unannotated, inputs={"x": "value"}, annotations={"value": float})

        with pytest.raises(ValueError, match="'value'"):
            build_port_table(function_map=plugin.functions())
