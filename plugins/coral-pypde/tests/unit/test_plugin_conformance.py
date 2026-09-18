"""This plugin's conformance to the ``coral_core.Plugin`` contract.

The ABC's *own* behaviour — that a subclass missing either method cannot be instantiated — belongs
to ``coral-core`` and is tested there; what belongs here is that **this** plugin satisfies it, and
that what it declares is coherent.

Nothing here imports ``coral_app``. Conformance is a fact about the plugin and the contract.
"""

import inspect
from typing import Any

import pytest
from coral_core import Plugin
from coral_plugin_pypde import PyPDEPlugin


@pytest.fixture
def plugin():
    """A live instance of this plugin."""
    return PyPDEPlugin()


class TestConformance:
    """It is a Plugin, and it can be instantiated — which means both methods are implemented."""

    def test_it_subclasses_the_contract(self):
        """GIVEN this plugin's class
        WHEN it is inspected
        THEN it is a subclass of coral_core.Plugin — which is how `load` recognises it."""
        assert issubclass(PyPDEPlugin, Plugin)

    def test_it_can_be_instantiated(self):
        """GIVEN this plugin's class
        WHEN it is instantiated with no arguments
        THEN it constructs.

        Not a formality: the ABC leaves both surface methods abstract, so a plugin that forgot one
        would raise TypeError here. `load` instantiates with no arguments, so that must work."""
        assert isinstance(PyPDEPlugin(), Plugin)

    def test_both_surfaces_are_dicts(self, plugin):
        """GIVEN a live plugin
        WHEN its two surface methods are called
        THEN each returns a dict, which is what the host merges."""
        assert isinstance(plugin.get_functions(), dict)
        assert isinstance(plugin.get_classes(), dict)

    def test_the_surfaces_are_stable_across_calls(self, plugin):
        """GIVEN a live plugin
        WHEN each surface is requested twice
        THEN the same names map to the same objects."""
        assert plugin.get_functions() == PyPDEPlugin().get_functions()
        assert plugin.get_classes() == PyPDEPlugin().get_classes()


class TestDeclaredSurface:
    """What this plugin puts on the table — and that it is fit to be a node type."""

    def test_it_declares_no_function_nodes(self, plugin):
        """GIVEN this plugin
        WHEN its function surface is read
        THEN it is empty.

        Asserted rather than left implicit: this is the first plugin whose whole surface is classes,
        so an empty ``get_functions()`` is a design statement, not an oversight. py-pde's API is
        objects that carry state between steps — a grid, a storage, an equation — and a free function
        would have nothing to hold.
        """
        assert plugin.get_functions() == {}

    def test_every_declared_class_is_a_class(self, plugin):
        """GIVEN this plugin's classes
        WHEN each value is inspected
        THEN it is a class: the host instantiates it for a constructor node."""
        for name, cls in plugin.get_classes().items():
            assert isinstance(cls, type), name

    def test_every_public_port_is_annotated(self, plugin):
        """GIVEN this plugin's constructors and public methods
        WHEN their signatures are read
        THEN no parameter and no return is left bare — the registry is annotation-driven."""
        for class_name, cls in plugin.get_classes().items():
            for method_name, method in _public_members(cls):
                signature = inspect.signature(method)
                for parameter in signature.parameters.values():
                    if parameter.name == "self":
                        continue
                    assert parameter.annotation is not inspect.Signature.empty, (
                        f"{class_name}.{method_name}:{parameter}"
                    )

    def test_no_public_port_is_annotated_any(self, plugin):
        """GIVEN this plugin's constructors and public methods
        WHEN their annotations are read
        THEN none of them is ``Any``.

        This is the property the whole surface is designed around. A port annotated ``Any`` makes the
        graph's edge check *skip* that edge, so a mis-wired simulation would only fail once the
        solver had run. Every wrapper here names a concrete type instead, and losing one to ``Any``
        would give that up silently — which is why it is asserted rather than left to review.
        """
        for class_name, cls in plugin.get_classes().items():
            for method_name, method in _public_members(cls):
                signature = inspect.signature(method)
                annotations = [
                    parameter.annotation
                    for parameter in signature.parameters.values()
                    if parameter.name != "self"
                ]
                if method_name != "__init__":
                    annotations.append(signature.return_annotation)
                assert Any not in annotations, f"{class_name}.{method_name}"

    def test_no_function_name_collides_with_a_class_name(self, plugin):
        """GIVEN this plugin's two surfaces
        WHEN their names are compared
        THEN they are disjoint.

        A node type is one string, so a name cannot mean both. The host refuses this too, in
        ``build_port_table`` — but only once a host is involved. Asserting it here keeps the failure
        local to the plugin that caused it."""
        assert not set(plugin.get_functions()) & set(plugin.get_classes())


def _public_members(cls):
    """The constructor and every public method of ``cls`` — the callables that become ports.

    Private members are excluded because the registry excludes them: ``PyPDEScalarField._holding``
    is annotated ``Any`` on purpose and is not a node.
    """
    return [("__init__", cls.__init__)] + [
        (name, getattr(cls, name))
        for name in dir(cls)
        if not name.startswith("_") and inspect.isfunction(getattr(cls, name))
    ]
