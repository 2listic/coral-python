"""``coral_app.legacy`` — declarations for plugins written against the subclassing contract.

Such a plugin hands over bare callables and classes, so which methods are nodes and how outputs are
named has to be read the way that contract always read them: every public pure-Python method is a
method node, and output names come from ``@outputs``.
"""

import pytest
from coral_app.legacy import class_declarations, function_declarations, is_legacy
from coral_app.nodeports import METHOD, Port, build_port_table, methods_of
from coral_core import Plugin, outputs


class Widget:
    """A class with public methods and assorted members that are not method nodes."""

    class_attribute = 42

    def __init__(self, size: float):
        self.size = size

    def resize(self, factor: float) -> float:
        return self.size * factor

    def _private(self, x: int) -> int:
        return x

    @staticmethod
    def helper(x: int) -> int:
        return x


def table(classes):
    """The port table of ``{key: class}`` read through the adapter."""
    return build_port_table(class_map=class_declarations(classes))


class TestWhichPluginsAreLegacy:
    """A plugin is read through the adapter when it overrides the subclassing contract."""

    def test_a_subclass_overriding_get_functions_is_legacy(self):
        """GIVEN a Plugin subclass overriding get_functions() and get_classes()
        WHEN it is classified
        THEN it is legacy."""

        class Subclassing(Plugin):
            def get_functions(self):
                return {}

            def get_classes(self):
                return {}

        assert is_legacy(Subclassing())

    def test_a_decorated_plugin_is_not_legacy(self):
        """GIVEN a plain Plugin instance
        WHEN it is classified
        THEN it is not legacy."""
        assert not is_legacy(Plugin())


class TestMethodEnumeration:
    """Which members of a class become method nodes."""

    def test_public_methods_are_entries(self):
        """GIVEN a class with a public method
        WHEN it is read through the adapter
        THEN the method is an entry, under its attribute name."""
        assert "Widget.resize" in methods_of(table({"Widget": Widget}), "Widget")

    def test_underscore_names_are_skipped(self):
        """GIVEN a class with a private method and dunder methods
        WHEN it is read through the adapter
        THEN no underscore-prefixed name becomes a node type."""
        assert not any("._" in node_type for node_type in table({"Widget": Widget}))

    def test_non_callable_attributes_are_skipped(self):
        """GIVEN a class carrying a plain (non-callable) class attribute
        WHEN it is read through the adapter
        THEN it does not become a node type."""
        assert "Widget.class_attribute" not in table({"Widget": Widget})

    def test_staticmethods_are_registered_as_methods(self):
        """GIVEN a class with a staticmethod
        WHEN it is read through the adapter
        THEN it registers as a method node with an instance at port 0, as it always did:
        ``getattr(cls, name)`` on a staticmethod yields the plain function."""
        entry = table({"Widget": Widget})["Widget.helper"]

        assert entry.kind == METHOD
        assert entry.inputs == [Port("self", Widget), Port("x", int)]


class TestOutputNames:
    """``@outputs`` is where a subclassing plugin's output names come from."""

    def test_a_function_s_names_are_read(self):
        """GIVEN a function marked with @outputs
        WHEN it is read through the adapter
        THEN its declaration carries the names."""

        @outputs("total")
        def add(a: float, b: float) -> float:
            return a + b

        assert function_declarations({"add": add})["add"].outputs == ("total",)

    def test_a_marked_init_is_refused(self):
        """GIVEN a class whose ``__init__`` carries @outputs
        WHEN it is read through the adapter
        THEN ValueError names the class: a constructor's output cannot be named."""

        class Labelled:
            @outputs("instance")
            def __init__(self, size: float):
                self.size = size

        with pytest.raises(ValueError, match="'Labelled'"):
            class_declarations({"Labelled": Labelled})

    def test_an_inherited_marked_init_is_refused_too(self):
        """GIVEN a subclass inheriting a marked ``__init__``
        WHEN it is read through the adapter alone
        THEN ValueError — the subclass's constructor is that same function."""

        class Labelled:
            @outputs("instance")
            def __init__(self, size: float):
                self.size = size

        class Derived(Labelled):
            pass

        with pytest.raises(ValueError, match="'Derived'"):
            class_declarations({"Derived": Derived})
