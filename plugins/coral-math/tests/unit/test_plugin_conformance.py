"""This plugin's conformance to the ``coral_core.Plugin`` contract.

Every plugin asserts this for itself. The ABC's *own* behaviour — that a subclass missing either
method cannot be instantiated — belongs to ``coral-core`` and is tested there; what belongs here is
that **this** plugin satisfies it, and that what it declares is coherent: named node types, annotated
callables, nothing accidentally exported twice.

Nothing here imports ``coral_app``. Conformance is a fact about the plugin and the contract, and needs
no host.
"""

import inspect

import pytest
from coral_core import Plugin
from coral_plugin_math import MathPlugin


@pytest.fixture
def plugin():
    """A live instance of this plugin."""
    return MathPlugin()


class TestConformance:
    """It is a Plugin, and it can be instantiated — which means both methods are implemented."""

    def test_it_subclasses_the_contract(self):
        """GIVEN this plugin's class
        WHEN it is inspected
        THEN it is a subclass of coral_core.Plugin — which is how `load` recognises it."""
        assert issubclass(MathPlugin, Plugin)

    def test_it_can_be_instantiated(self):
        """GIVEN this plugin's class
        WHEN it is instantiated with no arguments
        THEN it constructs.

        Not a formality: the ABC leaves both surface methods abstract, so a plugin that forgot one
        would raise TypeError here. `load` instantiates with no arguments, so that must work."""
        assert isinstance(MathPlugin(), Plugin)

    def test_both_surfaces_are_dicts(self, plugin):
        """GIVEN a live plugin
        WHEN its two surface methods are called
        THEN each returns a dict, which is what the host merges."""
        assert isinstance(plugin.get_functions(), dict)
        assert isinstance(plugin.get_classes(), dict)

    def test_the_surfaces_are_stable_across_calls(self, plugin):
        """GIVEN a live plugin
        WHEN each surface is requested twice
        THEN the same names map to the same objects.

        The host may build a map more than once per process (`register` then `run`), and a plugin that
        rebuilt its callables each time would defeat identity comparisons the host relies on."""
        assert plugin.get_functions() == MathPlugin().get_functions()
        assert plugin.get_classes() == MathPlugin().get_classes()


class TestDeclaredSurface:
    """What this plugin puts on the table — and that it is fit to be a node type."""

    def test_it_declares_the_expected_node_types(self, plugin):
        """GIVEN this plugin
        WHEN its function and class names are read
        THEN they are exactly the node types it means to contribute.

        An exact comparison, not a subset: adding or removing a node type is a change to what the
        platform can wire, so it should require editing this list on purpose."""
        assert set(plugin.get_functions()) == {
            "print_number",
            "add",
            "multiply",
            "math.sqrt",
            "math.sin",
            "math.cos",
            "math.pow",
            "test_tuple_return",
        }
        assert set(plugin.get_classes()) == {"Calculator"}

    def test_every_declared_function_is_callable(self, plugin):
        """GIVEN this plugin's functions
        WHEN each value is inspected
        THEN it is callable — the host will call it with no further ceremony."""
        for name, func in plugin.get_functions().items():
            assert callable(func), name

    def test_every_declared_class_is_a_class(self, plugin):
        """GIVEN this plugin's classes
        WHEN each value is inspected
        THEN it is a class: the host instantiates it for a constructor node."""
        for name, cls in plugin.get_classes().items():
            assert isinstance(cls, type), name

    def test_every_function_parameter_is_annotated(self, plugin):
        """GIVEN this plugin's functions
        WHEN their signatures are read
        THEN every parameter and every return carries an annotation.

        This is the bargain the host's registry and graph checks rest on: an unannotated port renders
        as `any` and makes the edge check *skip*, so a wrong wire is only found when the graph runs.
        Whether that happens is the plugin author's choice, and this plugin's choice is to annotate.
        """
        for name, func in plugin.get_functions().items():
            signature = inspect.signature(func)
            for parameter in signature.parameters.values():
                assert parameter.annotation is not inspect.Signature.empty, f"{name}:{parameter}"
            assert signature.return_annotation is not inspect.Signature.empty, name

    def test_every_public_method_is_annotated(self, plugin):
        """GIVEN this plugin's classes
        WHEN their public methods and constructors are read
        THEN every parameter and return is annotated, for the same reason as the functions."""
        for class_name, cls in plugin.get_classes().items():
            members = [("__init__", cls.__init__)] + [
                (name, getattr(cls, name))
                for name in dir(cls)
                if not name.startswith("_") and inspect.isfunction(getattr(cls, name))
            ]
            for method_name, method in members:
                signature = inspect.signature(method)
                for parameter in signature.parameters.values():
                    if parameter.name == "self":
                        continue
                    assert parameter.annotation is not inspect.Signature.empty, (
                        f"{class_name}.{method_name}:{parameter}"
                    )

    def test_no_function_name_collides_with_a_class_name(self, plugin):
        """GIVEN this plugin's two surfaces
        WHEN their names are compared
        THEN they are disjoint.

        A node type is one string, so a name cannot mean both. The host refuses this too — the two
        surfaces meet in ``build_port_table``, which raises ``DuplicateNodeTypeError`` — but only once
        a host is involved. Asserting it here keeps the failure local to the plugin that caused it,
        and needs nothing installed but this package."""
        assert not set(plugin.get_functions()) & set(plugin.get_classes())
