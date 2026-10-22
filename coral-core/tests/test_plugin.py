"""``Plugin`` — declaring node types with ``function`` / ``cls`` / ``method``.

What this package can judge on its own: which objects may be declared, the options' shapes, the
duplicates inside one plugin, and how a class's method node types are resolved through its MRO.
Everything that needs a signature — a label naming no parameter, an output count that does not
match the return annotation — is the host's check, not this package's.
"""

import math
from abc import ABC, abstractmethod
from fractions import Fraction

import pytest
from coral_core import ClassDeclaration, Declaration, MethodDeclaration, Plugin


def add(a: float, b: float) -> float:
    """A function declared in several tests."""
    return a + b


class Shape(ABC):
    """A class Python refuses to instantiate: ``area`` is abstract."""

    @abstractmethod
    def area(self) -> float: ...


class Square(Shape):
    """A concrete subclass of :class:`Shape`: an ABC's subclass is not abstract by inheritance."""

    def area(self) -> float:
        return 1.0


class TestTheThreeForms:
    """Each decorator is used bare, with options, or as a call — and returns its target unchanged."""

    def test_the_bare_form_returns_the_function(self):
        """GIVEN a plugin
        WHEN a function is decorated with the bare @plugin.function
        THEN the decorator returns that very function, declared under its __name__."""
        plugin = Plugin()

        def double(x: float) -> float:
            return 2 * x

        assert plugin.function(double) is double
        assert plugin.functions() == {"double": Declaration(double)}

    def test_the_form_with_options_returns_the_function(self):
        """GIVEN a plugin
        WHEN a function is decorated with @plugin.function(...) and options
        THEN the function is unchanged and the options are in its declaration."""
        plugin = Plugin()

        @plugin.function(
            name="math.pow",
            inputs={"x": "base"},
            outputs="power",
            annotations={"y": float},
        )
        def math_pow(x: float, y) -> float:
            return x**y

        assert math_pow(2.0, 3.0) == 8.0
        assert plugin.functions() == {
            "math.pow": Declaration(math_pow, {"x": "base"}, ("power",), {"y": float})
        }

    def test_the_call_form_declares_a_builtin(self):
        """GIVEN a builtin, which cannot be decorated where it is defined
        WHEN it is declared with plugin.function as a plain call
        THEN it is declared, with its options, and the builtin itself is returned."""
        plugin = Plugin()

        returned = plugin.function(
            math.atan2, name="math.atan2", annotations={"y": float, "x": float, "return": float}
        )

        assert returned is math.atan2
        assert plugin.functions()["math.atan2"] == Declaration(
            math.atan2, {}, None, {"y": float, "x": float, "return": float}
        )

    def test_a_class_and_its_methods_are_returned_unchanged(self):
        """GIVEN a class decorated with @plugin.cls and a method with @plugin.method
        WHEN the class is used
        THEN it behaves as an undecorated class: same object, method callable as usual."""
        plugin = Plugin()

        @plugin.cls
        class Counter:
            def __init__(self, start: int):
                self.count = start

            @plugin.method
            def bump(self) -> int:
                self.count += 1
                return self.count

        assert plugin.classes()["Counter"].target is Counter
        assert Counter(1).bump() == 2

    @pytest.mark.parametrize("decorator", ["cls", "method"])
    def test_the_call_form_returns_its_target(self, decorator):
        """GIVEN a class, or a plain function, declared with plugin.cls or plugin.method as a call
             with an option
        WHEN the call returns
        THEN it returns that very object."""

        def scale(self, factor: float) -> float: ...

        target = Fraction if decorator == "cls" else scale
        assert getattr(Plugin(), decorator)(target, name="renamed") is target


class TestClassDeclarations:
    """What ``classes()`` hands the host."""

    def test_only_declared_methods_are_method_nodes(self):
        """GIVEN a class with one declared method and one undeclared public method
        WHEN the plugin's classes are read
        THEN only the declared one is a method node type."""
        plugin = Plugin()

        @plugin.cls
        class Counter:
            @plugin.method
            def bump(self) -> int: ...

            def helper(self) -> int: ...

        assert list(plugin.classes()["Counter"].methods) == ["Counter.bump"]

    def test_a_class_declaration_carries_its_constructor_options(self):
        """GIVEN a class declared with a name, input labels and annotations
        WHEN the plugin's classes are read
        THEN it is keyed by that name, and carries the options for its constructor."""
        plugin = Plugin()

        @plugin.cls(name="Counter", inputs={"start": "initial"}, annotations={"step": int})
        class _Counter:
            def __init__(self, start: int, step): ...

        assert plugin.classes() == {
            "Counter": ClassDeclaration(_Counter, {"start": "initial"}, {"step": int}, {})
        }

    def test_a_method_node_is_keyed_by_class_key_and_name(self):
        """GIVEN a renamed class with a renamed method
        WHEN the plugin's classes are read
        THEN the method node type is `<class key>.<name>`, and its attribute is the real one."""
        plugin = Plugin()

        @plugin.cls(name="Counter")
        class _Counter:
            @plugin.method(name="current", outputs="value")
            def get(self) -> int: ...

        assert plugin.classes()["Counter"].methods == {
            "Counter.current": MethodDeclaration("get", Declaration(_Counter.get, {}, ("value",)))
        }

    def test_private_and_dunder_methods_may_be_declared(self):
        """GIVEN a class declaring a private method and a dunder other than the constructor
        WHEN the plugin's classes are read
        THEN both are method node types: being declared is what makes a node."""
        plugin = Plugin()

        @plugin.cls
        class Counter:
            @plugin.method
            def _peek(self) -> int: ...

            @plugin.method
            def __len__(self) -> int: ...

        assert set(plugin.classes()["Counter"].methods) == {"Counter._peek", "Counter.__len__"}

    def test_methods_follow_dir_order_of_their_attributes(self):
        """GIVEN methods declared in non-alphabetical order, one renamed to sort first
        WHEN the plugin's classes are read
        THEN they come in dir() order of their attribute names, not of their node names."""
        plugin = Plugin()

        @plugin.cls
        class Counter:
            @plugin.method
            def zeta(self) -> int: ...

            @plugin.method(name="aaa")
            def beta(self) -> int: ...

            @plugin.method
            def alpha(self) -> int: ...

        assert list(plugin.classes()["Counter"].methods) == [
            "Counter.alpha",
            "Counter.aaa",
            "Counter.zeta",
        ]

    def test_functions_and_classes_keep_declaration_order(self):
        """GIVEN functions and classes declared in non-alphabetical order
        WHEN the plugin's functions and classes are read
        THEN each keeps the order of declaration."""
        plugin = Plugin()
        plugin.function(add, name="zeta")
        plugin.function(add, name="alpha")
        plugin.cls(Fraction, name="Z")
        plugin.cls(int, name="A")

        assert list(plugin.functions()) == ["zeta", "alpha"]
        assert list(plugin.classes()) == ["Z", "A"]

    def test_a_method_is_found_whatever_the_metaclass_s_dir_says(self):
        """GIVEN a class whose metaclass redefines dir() to list nothing
        WHEN classes() resolves it
        THEN its declared method is still a method node."""
        plugin = Plugin()

        class Hiding(type):
            def __dir__(cls):
                return []

        @plugin.cls
        class Meter(metaclass=Hiding):
            @plugin.method
            def read(self) -> float:
                return 0.0

        assert list(plugin.classes()["Meter"].methods) == ["Meter.read"]


class TestResolutionIsLazy:
    """Method node types are resolved when the host asks, so declaration order does not matter."""

    def test_a_foreign_method_declared_before_its_class(self):
        """GIVEN a method of a library class declared as a call, before its class
        WHEN the class is declared afterwards and the plugin's classes are read
        THEN the method is a node type of it."""
        plugin = Plugin()
        plugin.method(
            Fraction.limit_denominator, annotations={"max_denominator": int, "return": Fraction}
        )
        plugin.cls(Fraction, annotations={"numerator": int, "denominator": int})

        assert plugin.classes()["Fraction"].methods == {
            "Fraction.limit_denominator": MethodDeclaration(
                "limit_denominator",
                Declaration(
                    Fraction.limit_denominator,
                    {},
                    None,
                    {"max_denominator": int, "return": Fraction},
                ),
            )
        }

    def test_a_foreign_method_declared_after_its_class(self):
        """GIVEN a library class declared first, and one of its methods after
        WHEN the plugin's classes are read
        THEN the method is a node type of it."""
        plugin = Plugin()
        plugin.cls(Fraction)
        plugin.method(Fraction.limit_denominator)

        assert list(plugin.classes()["Fraction"].methods) == ["Fraction.limit_denominator"]

    def test_a_method_of_no_registered_class_is_refused(self):
        """GIVEN a method declared in a class that is never registered
        WHEN the plugin's classes are read
        THEN ValueError naming the method: the declaration would be silently lost."""
        plugin = Plugin()

        class Unregistered:
            @plugin.method
            def lost(self) -> int: ...

        with pytest.raises(ValueError, match="Unregistered.lost"):
            plugin.classes()

    def test_a_method_wrapped_after_declaration_is_refused(self):
        """GIVEN a declared function then wrapped in staticmethod, in a registered class
        WHEN the plugin's classes are read
        THEN ValueError: the class no longer holds the declared function."""
        plugin = Plugin()

        @plugin.cls
        class Counter:
            @staticmethod
            @plugin.method
            def make() -> int: ...

        with pytest.raises(ValueError, match=r"Counter\.make"):
            plugin.classes()

    def test_two_methods_on_one_node_type_are_refused(self):
        """GIVEN two methods of one class, one renamed to the other's name
        WHEN the plugin's classes are read
        THEN ValueError naming both attributes."""
        plugin = Plugin()

        @plugin.cls
        class Counter:
            @plugin.method
            def total(self) -> int: ...

            @plugin.method(name="total")
            def sum(self) -> int: ...

        with pytest.raises(ValueError, match="'sum' and 'total'|'total' and 'sum'"):
            plugin.classes()


class TestInheritance:
    """A registered class has every method declared anywhere in its MRO."""

    def test_a_subclass_of_a_registered_base_has_its_methods(self):
        """GIVEN a registered base with a declared method, and a registered subclass
        WHEN the plugin's classes are read
        THEN both classes have the method, each under its own key."""
        plugin = Plugin()

        @plugin.cls
        class Base:
            @plugin.method(outputs="v")
            def value(self) -> int: ...

        @plugin.cls
        class Child(Base):
            pass

        classes = plugin.classes()
        assert list(classes["Base"].methods) == ["Base.value"]
        assert classes["Child"].methods["Child.value"] == MethodDeclaration(
            "value", Declaration(Base.value, {}, ("v",))
        )

    def test_a_subclass_of_an_unregistered_base_has_its_methods(self):
        """GIVEN an unregistered base with a declared method, and a registered subclass
        WHEN the plugin's classes are read
        THEN the subclass has the method, and the base's declaration is not refused."""
        plugin = Plugin()

        class Base:
            @plugin.method
            def value(self) -> int: ...

        @plugin.cls
        class Child(Base):
            pass

        assert list(plugin.classes()) == ["Child"]
        assert list(plugin.classes()["Child"].methods) == ["Child.value"]

    def test_an_undeclared_override_keeps_the_labels(self):
        """GIVEN a method declared with name=, inputs= and outputs=, overridden without a
             declaration
        WHEN the subclass's methods are read
        THEN the node runs the override, with the base's name, inputs and outputs."""
        plugin = Plugin()

        @plugin.cls
        class Base:
            @plugin.method(name="get", inputs={"x": "ex"}, outputs="v")
            def value(self, x: int) -> int: ...

        @plugin.cls
        class Child(Base):
            def value(self, x: int) -> int: ...

        assert plugin.classes()["Child"].methods == {
            "Child.get": MethodDeclaration("value", Declaration(Child.value, {"x": "ex"}, ("v",)))
        }

    def test_an_undeclared_override_of_an_annotated_declaration_is_refused(self):
        """GIVEN a method declared with annotations=, overridden without a declaration
        WHEN the subclass's methods are read
        THEN ValueError naming the class, the attribute and the annotated slots: annotations
             describe one function, so the override must be declared itself."""
        plugin = Plugin()

        @plugin.cls
        class Base:
            @plugin.method(annotations={"x": int})
            def value(self, x) -> int: ...

        @plugin.cls
        class Child(Base):
            def value(self, x: int) -> int: ...

        with pytest.raises(ValueError, match=r"'Child'.*'value'.*\['x'\].*plugin\.method"):
            plugin.classes()

    def test_a_redeclared_override_replaces_the_labels(self):
        """GIVEN a declared method, overridden in a subclass with a declaration of its own
        WHEN the subclass and its own subclass are read
        THEN both use the override's labels, and the base keeps its own."""
        plugin = Plugin()

        @plugin.cls
        class Base:
            @plugin.method(outputs="old")
            def value(self) -> int: ...

        @plugin.cls
        class Child(Base):
            @plugin.method(outputs="new")
            def value(self) -> int: ...

        @plugin.cls
        class GrandChild(Child):
            pass

        classes = plugin.classes()
        assert classes["Base"].methods["Base.value"].declaration.outputs == ("old",)
        assert classes["Child"].methods["Child.value"].declaration.outputs == ("new",)
        assert classes["GrandChild"].methods["GrandChild.value"].declaration.outputs == ("new",)

    def test_a_shadowed_declaration_is_not_refused(self):
        """GIVEN an unregistered base's declared method, overridden in the only registered class
        WHEN the plugin's classes are read
        THEN no error: the base's function is in the registered class's MRO, though shadowed."""
        plugin = Plugin()

        class Base:
            @plugin.method
            def value(self) -> int: ...

        @plugin.cls
        class Child(Base):
            def value(self) -> int: ...

        assert list(plugin.classes()["Child"].methods) == ["Child.value"]

    def test_an_override_that_is_not_a_function_is_refused(self):
        """GIVEN a declared method, overridden in a registered subclass by a plain attribute
        WHEN the plugin's classes are read
        THEN TypeError naming the subclass and the attribute."""
        plugin = Plugin()

        @plugin.cls
        class Base:
            @plugin.method
            def value(self) -> int: ...

        @plugin.cls
        class Child(Base):
            value = None

        with pytest.raises(TypeError, match="Child.*'value'"):
            plugin.classes()

    def test_a_non_function_override_in_an_unregistered_base_names_both_classes(self):
        """GIVEN a declared method, overridden by a property in an unregistered intermediate class
        WHEN a registered subclass of that class is read
        THEN TypeError naming the registered class and the class holding the override."""
        plugin = Plugin()

        class Base:
            @plugin.method
            def value(self) -> int: ...

        class Mid(Base):
            value = property(lambda self: 0)

        @plugin.cls
        class Leaf(Mid):
            pass

        with pytest.raises(
            TypeError, match=r"'Leaf': its base '.*Mid' overrides the method 'value'"
        ):
            plugin.classes()

    def test_an_annotated_override_in_an_unregistered_base_names_both_classes(self):
        """GIVEN a method declared with annotations=, overridden without a declaration in an
             unregistered intermediate class
        WHEN a registered subclass of that class is read
        THEN ValueError naming the registered class and the class holding the override."""
        plugin = Plugin()

        class Base:
            @plugin.method(annotations={"x": int})
            def value(self, x) -> int: ...

        class Mid(Base):
            def value(self, x: int) -> int: ...

        @plugin.cls
        class Leaf(Mid):
            pass

        with pytest.raises(
            ValueError, match=r"'Leaf': its base '.*Mid' overrides the method 'value'"
        ):
            plugin.classes()


class TestConstAndWrites:
    """``const=`` and ``writes=``: what a node modifies, carried to the host on its declaration."""

    def test_a_method_is_not_const_and_writes_nothing_by_default(self):
        """GIVEN a method declared with no option
        WHEN the class's methods are read
        THEN it is not const, and it writes no parameter: its instance is all it modifies."""
        plugin = Plugin()

        @plugin.cls
        class Counter:
            @plugin.method
            def bump(self, by: int) -> int: ...

        method = plugin.classes()["Counter"].methods["Counter.bump"]
        assert method.const is False
        assert method.declaration.writes == ()

    def test_const_and_writes_reach_the_method_declaration(self):
        """GIVEN a method declared with const=True and writes=
        WHEN the class's methods are read
        THEN its declaration carries both."""
        plugin = Plugin()

        @plugin.cls
        class Sorter:
            @plugin.method(const=True, writes="items")
            def sort_into(self, items: list) -> None: ...

        assert plugin.classes()["Sorter"].methods["Sorter.sort_into"] == MethodDeclaration(
            "sort_into", Declaration(Sorter.sort_into, writes=("items",)), const=True
        )

    def test_writes_reach_the_function_declaration(self):
        """GIVEN a function declared with writes= naming two parameters
        WHEN the plugin's functions are read
        THEN its declaration carries them, in the order given."""
        plugin = Plugin()
        plugin.function(add, writes=["b", "a"])
        assert plugin.functions()["add"].writes == ("b", "a")

    @pytest.mark.parametrize("writes", [None, (), []], ids=["omitted", "empty-tuple", "empty-list"])
    def test_no_written_parameter_is_an_empty_tuple(self, writes):
        """GIVEN writes= omitted, or an empty sequence
        WHEN the function is declared
        THEN it writes nothing: writing no parameter is a valid statement."""
        plugin = Plugin()
        plugin.function(add, writes=writes)
        assert plugin.functions()["add"].writes == ()


class TestOverridesPromiseNoLess:
    """An override may promise more than what it overrides, never less: ``const`` where its base
    is, and no parameter written that a base reads."""

    def test_an_undeclared_override_of_a_const_method_is_refused(self):
        """GIVEN a method declared const=True, overridden without a declaration
        WHEN the subclass's methods are read
        THEN ValueError naming the class, the attribute and the const declaration: an undeclared
             override is not const."""
        plugin = Plugin()

        @plugin.cls
        class Base:
            @plugin.method(const=True)
            def value(self) -> int: ...

        @plugin.cls
        class Child(Base):
            def value(self) -> int: ...

        with pytest.raises(
            ValueError, match=r"'Child'.*'value'.*Base\.value.*plugin\.method\(const=True\)"
        ):
            plugin.classes()

    def test_a_declared_override_of_a_const_method_must_be_const(self):
        """GIVEN a method declared const=True, overridden with a declaration without const=True
        WHEN the subclass's methods are read
        THEN ValueError naming both functions."""
        plugin = Plugin()

        @plugin.cls
        class Base:
            @plugin.method(const=True)
            def value(self) -> int: ...

        @plugin.cls
        class Child(Base):
            @plugin.method
            def value(self) -> int: ...

        with pytest.raises(ValueError, match=r"Base\.value.*Child\.value.*never less"):
            plugin.classes()

    def test_a_const_override_of_a_const_method_is_accepted(self):
        """GIVEN a method declared const=True, overridden with a declaration const=True too
        WHEN the subclass's methods are read
        THEN the override is const."""
        plugin = Plugin()

        @plugin.cls
        class Base:
            @plugin.method(const=True)
            def value(self) -> int: ...

        @plugin.cls
        class Child(Base):
            @plugin.method(const=True)
            def value(self) -> int: ...

        assert plugin.classes()["Child"].methods["Child.value"].const is True

    def test_a_const_override_of_a_writer_is_accepted(self):
        """GIVEN a method that is not const, overridden with a declaration const=True
        WHEN the subclass's methods are read
        THEN the override is const: it promises more than its base."""
        plugin = Plugin()

        @plugin.cls
        class Base:
            @plugin.method
            def value(self) -> int: ...

        @plugin.cls
        class Child(Base):
            @plugin.method(const=True)
            def value(self) -> int: ...

        classes = plugin.classes()
        assert classes["Base"].methods["Base.value"].const is False
        assert classes["Child"].methods["Child.value"].const is True

    def test_a_declared_override_may_not_write_what_its_base_reads(self):
        """GIVEN a method that reads its parameter, overridden with a declaration writing it under
             another name
        WHEN the subclass's methods are read
        THEN ValueError naming the parameter and the base: positions are compared, not names."""
        plugin = Plugin()

        @plugin.cls
        class Base:
            @plugin.method
            def fill(self, x: list) -> None: ...

        @plugin.cls
        class Child(Base):
            @plugin.method(writes="y")
            def fill(self, y: list) -> None: ...

        with pytest.raises(ValueError, match=r"'Child'.*'fill'.*\['y'\].*Base\.fill"):
            plugin.classes()

    def test_a_declared_override_may_write_less_than_its_base(self):
        """GIVEN a method writing its parameter, overridden with a declaration writing it under
             another name, and one writing nothing
        WHEN the subclasses' methods are read
        THEN both are accepted, each with its own writes=."""
        plugin = Plugin()

        @plugin.cls
        class Base:
            @plugin.method(writes="x")
            def fill(self, x: list) -> None: ...

        @plugin.cls
        class Renamed(Base):
            @plugin.method(writes="y")
            def fill(self, y: list) -> None: ...

        @plugin.cls
        class Reader(Base):
            @plugin.method
            def fill(self, x: list) -> None: ...

        classes = plugin.classes()
        assert classes["Renamed"].methods["Renamed.fill"].declaration.writes == ("y",)
        assert classes["Reader"].methods["Reader.fill"].declaration.writes == ()

    def test_an_undeclared_override_inherits_writes_and_const(self):
        """GIVEN a method that is not const and writes a parameter, overridden without a
             declaration
        WHEN the subclass's methods are read
        THEN the override keeps both: it runs behind the base's ports."""
        plugin = Plugin()

        @plugin.cls
        class Base:
            @plugin.method(writes="x")
            def fill(self, x: list) -> None: ...

        @plugin.cls
        class Child(Base):
            def fill(self, x: list) -> None: ...

        assert plugin.classes()["Child"].methods["Child.fill"] == MethodDeclaration(
            "fill", Declaration(Child.fill, writes=("x",)), const=False
        )

    def test_every_declared_ancestor_is_compared_not_only_the_nearest(self):
        """GIVEN a class deriving from two registered bases, one declaring a method that is not
             const and the other declaring it const=True, and overriding it without a declaration
        WHEN the class's methods are read
        THEN ValueError naming the const base, though the nearest declaration is not const: a
             node of the const base's type, given this class's instance, would run the override."""
        plugin = Plugin()

        @plugin.cls
        class Writer:
            @plugin.method
            def value(self) -> int: ...

        @plugin.cls
        class Reader:
            @plugin.method(const=True)
            def value(self) -> int: ...

        @plugin.cls
        class Both(Writer, Reader):
            def value(self) -> int: ...

        with pytest.raises(ValueError, match=r"'Both'.*'value'.*Reader\.value"):
            plugin.classes()

    def test_an_unregistered_class_in_between_is_compared_too(self):
        """GIVEN a const method, overridden without const=True in an unregistered intermediate
             class whose registered subclass inherits it
        WHEN the subclass's methods are read
        THEN ValueError naming the class holding the override and the const declaration."""
        plugin = Plugin()

        @plugin.cls
        class Base:
            @plugin.method(const=True)
            def value(self) -> int: ...

        class Mid(Base):
            @plugin.method
            def value(self) -> int: ...

        @plugin.cls
        class Leaf(Mid):
            pass

        with pytest.raises(ValueError, match=r"'Leaf': its base '.*Mid'.*Base\.value"):
            plugin.classes()

    def test_an_undeclared_override_reordering_a_written_parameter_is_refused(self):
        """GIVEN a method writing its first parameter, overridden without a declaration by a
             function taking the same parameters in the other order
        WHEN the subclass's methods are read
        THEN ValueError naming the parameter and the base: the override inherits the name, so it
             writes its second port, which the base reads."""
        plugin = Plugin()

        @plugin.cls
        class Base:
            @plugin.method(writes="a")
            def fill(self, a: list, b: list) -> None: ...

        @plugin.cls
        class Child(Base):
            def fill(self, b: list, a: list) -> None: ...

        with pytest.raises(ValueError, match=r"'Child'.*'fill'.*\['a'\].*Base\.fill"):
            plugin.classes()

    def test_an_undeclared_override_missing_an_inherited_written_parameter_is_refused(self):
        """GIVEN a method writing a parameter, overridden without a declaration by a function
             that has no parameter of that name
        WHEN the subclass's methods are read
        THEN ValueError naming the parameter: the inherited writes= cannot apply, so the override
             must be declared itself."""
        plugin = Plugin()

        @plugin.cls
        class Base:
            @plugin.method(writes="a")
            def fill(self, a: list) -> None: ...

        @plugin.cls
        class Child(Base):
            def fill(self, x: list) -> None: ...

        with pytest.raises(ValueError, match=r"'Child'.*'fill'.*\['a'\].*plugin\.method"):
            plugin.classes()

    def test_a_declared_method_s_writes_is_left_to_the_host(self):
        """GIVEN a method, overriding nothing, whose writes= names no parameter of it
        WHEN the plugin's classes are read
        THEN no error here: there is no override to blame, and the host checks writes= against
             the signature, as it checks inputs=."""
        plugin = Plugin()

        @plugin.cls
        class Counter:
            @plugin.method(writes="nope")
            def bump(self, by: int) -> int: ...

        assert plugin.classes()["Counter"].methods["Counter.bump"].declaration.writes == ("nope",)


class TestAbstractClasses:
    """A class that only types sockets: declared with ``abstract=``, or detected with
    ``inspect.isabstract``."""

    @pytest.mark.parametrize("target", [Fraction, Square])
    def test_a_class_python_can_instantiate_is_not_abstract(self, target):
        """GIVEN a concrete class declared without abstract=
        WHEN the plugin's classes are read
        THEN it is not abstract: its constructor is a node type."""
        plugin = Plugin()
        plugin.cls(target)
        assert plugin.classes()[target.__name__].abstract is False

    def test_a_class_python_cannot_instantiate_is_abstract(self):
        """GIVEN a class with an unimplemented abstract method, declared without abstract=
        WHEN the plugin's classes are read
        THEN it is abstract: Python refuses to build it, so it offers no constructor."""
        plugin = Plugin()
        plugin.cls(Shape)
        assert plugin.classes()["Shape"].abstract is True

    @pytest.mark.parametrize("target", [Fraction, Shape])
    def test_abstract_true_wins(self, target):
        """GIVEN abstract=True, on a concrete class and on one Python cannot instantiate
        WHEN the plugin's classes are read
        THEN both are abstract."""
        plugin = Plugin()
        plugin.cls(target, abstract=True)
        assert plugin.classes()[target.__name__].abstract is True

    def test_abstract_false_keeps_a_concrete_class_a_constructor(self):
        """GIVEN abstract=False on a concrete class
        WHEN the plugin's classes are read
        THEN it is not abstract, as if the option were omitted."""
        plugin = Plugin()
        plugin.cls(Square, abstract=False)
        assert plugin.classes()["Square"].abstract is False

    def test_abstract_false_is_refused_on_a_class_python_cannot_instantiate(self):
        """GIVEN abstract=False on a class with an unimplemented abstract method
        WHEN it is declared
        THEN ValueError naming the method: its constructor node would fail every time it ran."""
        with pytest.raises(ValueError, match=r"abstract=False.*\['area'\]"):
            Plugin().cls(Shape, abstract=False)

    @pytest.mark.parametrize(
        "option",
        [{"inputs": {"x": "label"}}, {"annotations": {"x": int}}],
        ids=["inputs", "annotations"],
    )
    @pytest.mark.parametrize(
        "target, abstract", [(Fraction, True), (Shape, None)], ids=["declared", "detected"]
    )
    def test_constructor_options_are_refused_on_an_abstract_class(self, target, abstract, option):
        """GIVEN an abstract class, declared so or detected, with inputs= or annotations=
        WHEN it is declared
        THEN ValueError: both describe constructor parameters, and it has no constructor."""
        with pytest.raises(ValueError, match="the class is abstract"):
            Plugin().cls(target, abstract=abstract, **option)

    def test_an_abstract_class_may_be_renamed(self):
        """GIVEN an abstract class declared with name=
        WHEN the plugin's classes are read
        THEN it is keyed by that name: the key is the socket type it gives."""
        plugin = Plugin()
        plugin.cls(Shape, name="Figure")
        assert plugin.classes()["Figure"].abstract is True

    def test_a_method_declared_on_an_abstract_class_is_a_node_of_it_and_of_its_subclass(self):
        """GIVEN an abstract base declaring a method, and a registered concrete subclass
        WHEN the plugin's classes are read
        THEN both have the method node: it runs on whichever concrete instance reaches it."""
        plugin = Plugin()

        @plugin.cls(abstract=True)
        class Base:
            @plugin.method
            def value(self) -> int: ...

        @plugin.cls
        class Child(Base):
            pass

        classes = plugin.classes()
        assert list(classes["Base"].methods) == ["Base.value"]
        assert list(classes["Child"].methods) == ["Child.value"]
        assert classes["Base"].abstract and not classes["Child"].abstract

    def test_abstract_must_be_a_bool(self):
        """GIVEN abstract= that is not a bool
        WHEN a class is declared
        THEN TypeError: a truthy value is not a decision."""
        with pytest.raises(TypeError, match="abstract= takes a bool"):
            Plugin().cls(Fraction, abstract="yes")


class TestAcrossPlugins:
    """A plugin sees only its own declarations."""

    def test_another_plugins_declarations_are_not_inherited(self):
        """GIVEN a method declared by plugin A, and a subclass registered by plugin B
        WHEN plugin B's classes are read
        THEN the subclass has no method node types."""
        plugin_a, plugin_b = Plugin(), Plugin()

        @plugin_a.cls
        class Base:
            @plugin_a.method
            def value(self) -> int: ...

        @plugin_b.cls
        class Child(Base):
            pass

        assert plugin_b.classes()["Child"].methods == {}

    def test_another_plugins_method_can_be_declared_again(self):
        """GIVEN a method declared by plugin A
        WHEN plugin B declares it too, as a call, and registers a subclass
        THEN plugin B's subclass has the method, with B's labels."""
        plugin_a, plugin_b = Plugin(), Plugin()

        @plugin_a.cls
        class Base:
            @plugin_a.method(outputs="a")
            def value(self) -> int: ...

        @plugin_b.cls
        class Child(Base):
            pass

        plugin_b.method(Base.value, outputs="b")

        assert plugin_b.classes()["Child"].methods["Child.value"].declaration.outputs == ("b",)
        assert plugin_a.classes()["Base"].methods["Base.value"].declaration.outputs == ("a",)

    def test_each_plugin_holds_only_its_own_declarations(self):
        """GIVEN two plugins, one declaring a function and the other a class
        WHEN each is read
        THEN each holds only what was declared on it: there is no shared registry."""
        first, second = Plugin(), Plugin()
        first.function(add)
        second.cls(Fraction)

        assert list(first.functions()) == ["add"] and first.classes() == {}
        assert second.functions() == {} and list(second.classes()) == ["Fraction"]


class TestTargetsAreRefused:
    """Each decorator takes one kind of object, and refuses the others at once."""

    def test_a_class_is_not_a_function(self):
        """GIVEN a class
        WHEN it is declared with plugin.function
        THEN TypeError pointing at plugin.cls."""
        with pytest.raises(TypeError, match="plugin.cls"):
            Plugin().function(Fraction)

    def test_a_non_callable_is_not_a_function(self):
        """GIVEN a string
        WHEN it is declared with plugin.function
        THEN TypeError."""
        with pytest.raises(TypeError, match="callable"):
            Plugin().function("add")

    def test_a_function_is_not_a_class(self):
        """GIVEN a function
        WHEN it is declared with plugin.cls
        THEN TypeError."""
        with pytest.raises(TypeError, match="only a class"):
            Plugin().cls(add)

    @pytest.mark.parametrize("decorator", ["function", "cls", "method"])
    def test_none_is_refused(self, decorator):
        """GIVEN None, as a failed lookup such as getattr(module, "name", None) returns
        WHEN it is passed to a decorator as its target
        THEN TypeError: None is a target that is not one, not the decorator used with options."""
        with pytest.raises(TypeError):
            getattr(Plugin(), decorator)(None)

    @pytest.mark.parametrize(
        "target",
        [staticmethod(add), classmethod(add), property(add), math.atan2],
        ids=["staticmethod", "classmethod", "property", "builtin"],
    )
    def test_only_a_plain_function_is_a_method(self, target):
        """GIVEN a staticmethod, classmethod, property or builtin
        WHEN it is declared with plugin.method
        THEN TypeError."""
        with pytest.raises(TypeError, match="plain function"):
            Plugin().method(target)

    @pytest.mark.parametrize("constructor", ["__init__", "__new__"])
    def test_a_constructor_is_not_a_method(self, constructor):
        """GIVEN a class's __init__ or __new__
        WHEN it is declared with plugin.method
        THEN ValueError: the constructor is the class's own node type."""

        def func(self): ...

        func.__name__ = constructor

        with pytest.raises(ValueError, match="plugin.cls"):
            Plugin().method(func)

    def test_a_declared_method_held_as_the_constructor_is_refused(self):
        """GIVEN a function declared with plugin.method, then assigned as a class's __init__
        WHEN the class's methods are resolved
        THEN ValueError naming the class: the constructor is the class's own node type."""
        plugin = Plugin()

        @plugin.method
        def setup(self, size: float): ...

        @plugin.cls
        class Box:
            __init__ = setup

        with pytest.raises(ValueError, match=r"'Box'.*'__init__'"):
            plugin.classes()

    def test_a_callable_without_a_name_needs_one(self):
        """GIVEN a callable with no __name__
        WHEN it is declared with plugin.function without name=
        THEN TypeError asking for name=."""

        class Callable_:
            def __call__(self, x: float) -> float: ...

        with pytest.raises(TypeError, match="pass name="):
            Plugin().function(Callable_())


class TestOptionsAreRefused:
    """What can be judged without the signature is refused at the decorator — at import."""

    @pytest.mark.parametrize("decorator", ["function", "cls", "method"])
    def test_a_name_must_be_a_string(self, decorator):
        """GIVEN name= that is not a string
        WHEN any decorator is applied
        THEN TypeError."""
        target = Fraction if decorator == "cls" else add
        with pytest.raises(TypeError, match="name= takes a string"):
            getattr(Plugin(), decorator)(target, name=3)

    @pytest.mark.parametrize("decorator", ["function", "cls", "method"])
    def test_a_name_cannot_be_empty(self, decorator):
        """GIVEN name=""
        WHEN any decorator is applied
        THEN ValueError."""
        target = Fraction if decorator == "cls" else add
        with pytest.raises(ValueError, match="cannot be empty"):
            getattr(Plugin(), decorator)(target, name="")

    @pytest.mark.parametrize("decorator", ["cls", "method"])
    def test_a_class_or_method_name_cannot_contain_a_dot(self, decorator):
        """GIVEN name= containing a dot, for a class or a method
        WHEN the decorator is applied
        THEN ValueError: `A.b` + `c` and `A` + `b.c` would be one node type."""
        target = Fraction if decorator == "cls" else add
        with pytest.raises(ValueError, match="cannot contain '.'"):
            getattr(Plugin(), decorator)(target, name="a.b")

    def test_a_function_name_may_contain_a_dot(self):
        """GIVEN name= containing a dot, for a function
        WHEN it is declared
        THEN it is accepted, as in `math.sqrt`."""
        plugin = Plugin()
        plugin.function(add, name="math.add")
        assert list(plugin.functions()) == ["math.add"]

    @pytest.mark.parametrize("decorator", ["function", "cls", "method"])
    def test_an_empty_default_name_is_refused(self, decorator):
        """GIVEN a target whose __name__ is empty, declared without name=
        WHEN any decorator is applied
        THEN ValueError asking for name=."""

        def func(self): ...

        func.__name__ = ""
        target = type("", (), {}) if decorator == "cls" else func
        with pytest.raises(ValueError, match="cannot be empty; pass name="):
            getattr(Plugin(), decorator)(target)

    @pytest.mark.parametrize("decorator", ["cls", "method"])
    def test_a_dotted_default_name_is_refused_for_a_class_or_method(self, decorator):
        """GIVEN a class or method whose __name__ contains a dot, declared without name=
        WHEN the decorator is applied
        THEN ValueError asking for name=: the default obeys the rule an explicit name does."""

        def func(self): ...

        func.__name__ = "a.b"
        target = type("a.b", (), {}) if decorator == "cls" else func
        with pytest.raises(ValueError, match=r"cannot contain '\.'.*pass name="):
            getattr(Plugin(), decorator)(target)

    @pytest.mark.parametrize("decorator", ["function", "method"])
    @pytest.mark.parametrize(
        "outputs",
        [3, ("a", 3), {"a": "b"}],
        ids=["not-a-sequence", "non-string-name", "a-dict"],
    )
    def test_outputs_must_be_strings(self, outputs, decorator):
        """GIVEN outputs= that is not a name or a sequence of names
        WHEN plugin.function or plugin.method is applied
        THEN TypeError."""
        with pytest.raises(TypeError, match="outputs= takes"):
            getattr(Plugin(), decorator)(add, outputs=outputs)

    @pytest.mark.parametrize("decorator", ["function", "method"])
    @pytest.mark.parametrize(
        "outputs, message",
        [((), "at least one"), (("a", ""), "cannot be empty"), (("a", "a"), "distinct")],
        ids=["none", "empty", "repeated"],
    )
    def test_outputs_must_be_distinct_non_empty_names(self, outputs, message, decorator):
        """GIVEN no output name, an empty one, or a repeated one
        WHEN plugin.function or plugin.method is applied
        THEN ValueError."""
        with pytest.raises(ValueError, match=message):
            getattr(Plugin(), decorator)(add, outputs=outputs)

    def test_a_plain_string_is_one_output_name(self):
        """GIVEN outputs= as a plain string
        WHEN the function is declared
        THEN it is one name, not one name per character."""
        plugin = Plugin()
        plugin.function(add, outputs="sum")
        assert plugin.functions()["add"].outputs == ("sum",)

    def test_a_list_of_names_is_accepted(self):
        """GIVEN outputs= as a list of names
        WHEN the function is declared
        THEN the names are kept, in order, as a tuple."""
        plugin = Plugin()
        plugin.function(add, outputs=["sum", "carry"])
        assert plugin.functions()["add"].outputs == ("sum", "carry")

    def test_a_class_takes_no_outputs(self):
        """GIVEN outputs= on plugin.cls
        WHEN it is applied
        THEN TypeError: a constructor's output is the instance, which carries no name."""
        with pytest.raises(TypeError):
            Plugin().cls(Fraction, outputs="value")

    @pytest.mark.parametrize("decorator", ["function", "cls", "method"])
    @pytest.mark.parametrize(
        "inputs",
        [["a"], {1: "one"}, {"a": 1}],
        ids=["not-a-dict", "non-string-key", "non-string-label"],
    )
    def test_inputs_must_map_strings_to_strings(self, inputs, decorator):
        """GIVEN inputs= that is not a dict of str -> str
        WHEN any decorator is applied
        THEN TypeError."""
        target = Fraction if decorator == "cls" else add
        with pytest.raises(TypeError, match="inputs= takes"):
            getattr(Plugin(), decorator)(target, inputs=inputs)

    @pytest.mark.parametrize("decorator", ["function", "cls", "method"])
    def test_an_input_label_cannot_be_empty(self, decorator):
        """GIVEN inputs= with an empty label
        WHEN any decorator is applied
        THEN ValueError naming the parameter."""
        target = Fraction if decorator == "cls" else add
        with pytest.raises(ValueError, match="'a'"):
            getattr(Plugin(), decorator)(target, inputs={"a": ""})

    @pytest.mark.parametrize("decorator", ["function", "cls", "method"])
    @pytest.mark.parametrize("annotations", [[float], {1: float}], ids=["not-a-dict", "int-key"])
    def test_annotations_must_be_keyed_by_strings(self, annotations, decorator):
        """GIVEN annotations= that is not a dict with str keys
        WHEN any decorator is applied
        THEN TypeError."""
        target = Fraction if decorator == "cls" else add
        with pytest.raises(TypeError, match="annotations= takes"):
            getattr(Plugin(), decorator)(target, annotations=annotations)

    @pytest.mark.parametrize("decorator", ["function", "cls", "method"])
    def test_an_annotation_cannot_be_a_string(self, decorator):
        """GIVEN annotations= giving a type by its name, as a string
        WHEN any decorator is applied
        THEN TypeError naming the key: a string is never resolved, so the port would silently
        become `any`."""
        target = Fraction if decorator == "cls" else add
        with pytest.raises(TypeError, match=r"not their names: \['a'\]"):
            getattr(Plugin(), decorator)(target, annotations={"a": "float"})

    @pytest.mark.parametrize("decorator", ["function", "method"])
    @pytest.mark.parametrize(
        "writes",
        [3, ("a", 3), {"a": "b"}],
        ids=["not-a-sequence", "non-string-name", "a-dict"],
    )
    def test_writes_must_be_strings(self, writes, decorator):
        """GIVEN writes= that is not a parameter name or a sequence of them
        WHEN plugin.function or plugin.method is applied
        THEN TypeError."""
        with pytest.raises(TypeError, match="writes= takes"):
            getattr(Plugin(), decorator)(add, writes=writes)

    @pytest.mark.parametrize("decorator", ["function", "method"])
    @pytest.mark.parametrize(
        "writes, message",
        [(("a", ""), "cannot be empty"), (("a", "a"), "once")],
        ids=["empty", "repeated"],
    )
    def test_writes_must_be_distinct_non_empty_names(self, writes, message, decorator):
        """GIVEN writes= with an empty name, or a name given twice
        WHEN plugin.function or plugin.method is applied
        THEN ValueError."""
        with pytest.raises(ValueError, match=message):
            getattr(Plugin(), decorator)(add, writes=writes)

    def test_a_plain_string_is_one_written_parameter(self):
        """GIVEN writes= as a plain string
        WHEN the function is declared
        THEN it is one name, not one name per character."""
        plugin = Plugin()
        plugin.function(add, writes="ab")
        assert plugin.functions()["add"].writes == ("ab",)

    def test_a_class_takes_no_writes(self):
        """GIVEN writes= on plugin.cls
        WHEN it is applied
        THEN TypeError: a constructor modifies none of its inputs."""
        with pytest.raises(TypeError):
            Plugin().cls(Fraction, writes="numerator")

    @pytest.mark.parametrize("const", [1, "yes", None], ids=["int", "str", "none"])
    def test_const_must_be_a_bool(self, const):
        """GIVEN const= that is not a bool
        WHEN plugin.method is applied
        THEN TypeError."""
        with pytest.raises(TypeError, match="const= takes a bool"):
            Plugin().method(add, const=const)

    @pytest.mark.parametrize("decorator", ["function", "cls"])
    def test_only_a_method_takes_const(self, decorator):
        """GIVEN const= on plugin.function or plugin.cls
        WHEN it is applied
        THEN TypeError: const= concerns a method's instance, which they do not have."""
        target = Fraction if decorator == "cls" else add
        with pytest.raises(TypeError):
            getattr(Plugin(), decorator)(target, const=True)


class TestDuplicatesInOnePlugin:
    """One plugin cannot declare one node type twice."""

    def test_a_function_name_used_twice_is_refused(self):
        """GIVEN a function declared under a name
        WHEN another function is declared under the same name
        THEN ValueError."""
        plugin = Plugin()
        plugin.function(add)
        with pytest.raises(ValueError, match="already declared"):
            plugin.function(math.hypot, name="add")

    def test_a_function_name_used_by_a_class_is_refused(self):
        """GIVEN a function declared under a name
        WHEN a class is declared under the same name
        THEN ValueError: one name, two kinds of node."""
        plugin = Plugin()
        plugin.function(add, name="Fraction")
        with pytest.raises(ValueError, match="already declared"):
            plugin.cls(Fraction)

    def test_a_class_key_used_by_a_function_is_refused(self):
        """GIVEN a class declared under a key
        WHEN a function is declared under the same name
        THEN ValueError."""
        plugin = Plugin()
        plugin.cls(Fraction)
        with pytest.raises(ValueError, match="already declared"):
            plugin.function(add, name="Fraction")

    def test_a_class_registered_twice_is_refused(self):
        """GIVEN a class declared once
        WHEN it is declared again under another key
        THEN ValueError naming the first key."""
        plugin = Plugin()
        plugin.cls(Fraction)
        with pytest.raises(ValueError, match="'Fraction'"):
            plugin.cls(Fraction, name="Ratio")

    def test_one_key_for_two_classes_is_refused(self):
        """GIVEN a class registered under its name
        WHEN a different class is registered under the same key
        THEN ValueError: one key names one constructor node type."""
        plugin = Plugin()

        class Other:
            pass

        plugin.cls(Fraction)
        with pytest.raises(ValueError, match="already declared"):
            plugin.cls(Other, name="Fraction")

    def test_a_method_declared_twice_is_refused(self):
        """GIVEN a method declared once
        WHEN it is declared again
        THEN ValueError."""
        plugin = Plugin()
        plugin.method(Fraction.limit_denominator)
        with pytest.raises(ValueError, match="already declared"):
            plugin.method(Fraction.limit_denominator, name="limit")

    def test_one_function_under_two_names_is_an_alias(self):
        """GIVEN a function declared under its name
        WHEN it is declared again under another name
        THEN both node types exist, running the same function."""
        plugin = Plugin()
        plugin.function(add)
        plugin.function(add, name="plus")
        assert {n: d.target for n, d in plugin.functions().items()} == {"add": add, "plus": add}


class TestDeclarationsAreReadOnly:
    """What the host receives cannot change the plugin it came from."""

    def test_a_function_s_options_cannot_be_changed_through_functions(self):
        """GIVEN a function declared with inputs= and annotations=
        WHEN a caller tries to change them on what functions() returned
        THEN TypeError, and the plugin still holds what was declared."""
        plugin = Plugin()
        plugin.function(math.atan2, inputs={"y": "rise"}, annotations={"return": float})
        declaration = plugin.functions()["atan2"]

        with pytest.raises(TypeError):
            declaration.inputs["y"] = "changed"
        with pytest.raises(TypeError):
            declaration.annotations["return"] = int

        assert plugin.functions()["atan2"].inputs == {"y": "rise"}
        assert plugin.functions()["atan2"].annotations == {"return": float}

    def test_a_class_s_options_cannot_be_changed_through_classes(self):
        """GIVEN a class declared with inputs= and annotations=
        WHEN a caller tries to change them on what classes() returned
        THEN TypeError, and the plugin still holds what was declared."""
        plugin = Plugin()

        class Box:
            def __init__(self, size): ...

        plugin.cls(Box, inputs={"size": "side"}, annotations={"size": float})
        declaration = plugin.classes()["Box"]

        with pytest.raises(TypeError):
            declaration.inputs["size"] = "changed"
        with pytest.raises(TypeError):
            declaration.annotations["size"] = int

        assert plugin.classes()["Box"].inputs == {"size": "side"}
        assert plugin.classes()["Box"].annotations == {"size": float}

    def test_a_method_s_options_cannot_be_changed_through_classes(self):
        """GIVEN a method declared with inputs= and annotations=
        WHEN a caller tries to change them on what classes() returned
        THEN TypeError, and the plugin still holds what was declared."""
        plugin = Plugin()

        @plugin.cls
        class Meter:
            @plugin.method(inputs={"scale": "factor"}, annotations={"scale": float})
            def read(self, scale) -> float: ...

        declaration = plugin.classes()["Meter"].methods["Meter.read"].declaration

        with pytest.raises(TypeError):
            declaration.inputs["scale"] = "changed"
        with pytest.raises(TypeError):
            declaration.annotations["scale"] = int

        method = plugin.classes()["Meter"].methods["Meter.read"].declaration
        assert method.inputs == {"scale": "factor"}
        assert method.annotations == {"scale": float}

    def test_a_class_s_methods_cannot_be_changed(self):
        """GIVEN a class declared with one method
        WHEN a caller tries to add a method node to its declaration
        THEN TypeError, and the plugin still resolves the same methods."""
        plugin = Plugin()

        @plugin.cls
        class Meter:
            @plugin.method
            def read(self) -> float:
                return 0.0

        declaration = plugin.classes()["Meter"]
        with pytest.raises(TypeError):
            declaration.methods["Meter.extra"] = declaration.methods["Meter.read"]

        assert list(plugin.classes()["Meter"].methods) == ["Meter.read"]
