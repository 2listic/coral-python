"""``Plugin`` — declaring node types with ``function`` / ``cls`` / ``method``.

What this package can judge on its own: which objects may be declared, the options' shapes, the
duplicates inside one plugin, and how a class's method node types are resolved through its MRO.
Everything that needs a signature — a label naming no parameter, an output count that does not
match the return annotation — is the host's check, not this package's.
"""

import math
from fractions import Fraction

import pytest
from coral_core import ClassDeclaration, Declaration, MethodDeclaration, Plugin


def add(a: float, b: float) -> float:
    """A function declared in several tests."""
    return a + b


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

        with pytest.raises(ValueError, match="staticmethod"):
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

    def test_an_undeclared_override_keeps_the_labels_but_not_the_annotations(self):
        """GIVEN a declared method with every option, overridden without a declaration
        WHEN the subclass's methods are read
        THEN the node runs the override, with the name, inputs and outputs but no annotations."""
        plugin = Plugin()

        @plugin.cls
        class Base:
            @plugin.method(name="get", inputs={"x": "ex"}, outputs="v", annotations={"x": int})
            def value(self, x) -> int: ...

        @plugin.cls
        class Child(Base):
            def value(self, x: int) -> int: ...

        assert plugin.classes()["Child"].methods == {
            "Child.get": MethodDeclaration("value", Declaration(Child.value, {"x": "ex"}, ("v",)))
        }

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

    @pytest.mark.parametrize(
        "outputs",
        [3, ("a", 3), {"a": "b"}],
        ids=["not-a-sequence", "non-string-name", "a-dict"],
    )
    def test_outputs_must_be_strings(self, outputs):
        """GIVEN outputs= that is not a name or a sequence of names
        WHEN the decorator is applied
        THEN TypeError."""
        with pytest.raises(TypeError, match="outputs= takes"):
            Plugin().function(add, outputs=outputs)

    @pytest.mark.parametrize(
        "outputs, message",
        [((), "at least one"), (("a", ""), "cannot be empty"), (("a", "a"), "distinct")],
        ids=["none", "empty", "repeated"],
    )
    def test_outputs_must_be_distinct_non_empty_names(self, outputs, message):
        """GIVEN no output name, an empty one, or a repeated one
        WHEN the decorator is applied
        THEN ValueError."""
        with pytest.raises(ValueError, match=message):
            Plugin().method(add, outputs=outputs)

    def test_a_plain_string_is_one_output_name(self):
        """GIVEN outputs= as a plain string
        WHEN the function is declared
        THEN it is one name, not one name per character."""
        plugin = Plugin()
        plugin.function(add, outputs="sum")
        assert plugin.functions()["add"].outputs == ("sum",)

    def test_a_class_takes_no_outputs(self):
        """GIVEN outputs= on plugin.cls
        WHEN it is applied
        THEN TypeError: a constructor's output is the instance, which carries no name."""
        with pytest.raises(TypeError):
            Plugin().cls(Fraction, outputs="value")

    @pytest.mark.parametrize(
        "inputs",
        [["a"], {1: "one"}, {"a": 1}],
        ids=["not-a-dict", "non-string-key", "non-string-label"],
    )
    def test_inputs_must_map_strings_to_strings(self, inputs):
        """GIVEN inputs= that is not a dict of str -> str
        WHEN the decorator is applied
        THEN TypeError."""
        with pytest.raises(TypeError, match="inputs= takes"):
            Plugin().function(add, inputs=inputs)

    def test_an_input_label_cannot_be_empty(self):
        """GIVEN inputs= with an empty label
        WHEN the decorator is applied
        THEN ValueError naming the parameter."""
        with pytest.raises(ValueError, match="'a'"):
            Plugin().function(add, inputs={"a": ""})

    @pytest.mark.parametrize("annotations", [[float], {1: float}], ids=["not-a-dict", "int-key"])
    def test_annotations_must_be_keyed_by_strings(self, annotations):
        """GIVEN annotations= that is not a dict with str keys
        WHEN the decorator is applied
        THEN TypeError."""
        with pytest.raises(TypeError, match="annotations= takes"):
            Plugin().function(add, annotations=annotations)


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
