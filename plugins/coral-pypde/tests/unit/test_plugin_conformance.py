"""This plugin's conformance to the ``coral_core.Plugin`` contract.

How a ``Plugin`` declares and resolves node types belongs to ``coral-core`` and is tested there;
what belongs here is that **this** plugin is one, and that what it declares is coherent.

Nothing here imports ``coral_app``. Conformance is a fact about the plugin and the contract.
"""

import inspect
from typing import Any

from coral_core import Plugin
from coral_plugin_pypde import plugin


class TestConformance:
    """It is a Plugin instance, and its declarations resolve."""

    def test_it_is_a_plugin_instance(self):
        """GIVEN this plugin's ``plugin``
        WHEN it is inspected
        THEN it is a coral_core.Plugin instance — which is how `load` recognises it."""
        assert isinstance(plugin, Plugin)

    def test_both_surfaces_are_dicts(self):
        """GIVEN this plugin
        WHEN its declarations are resolved
        THEN each surface is a dict, which is what the host merges."""
        assert isinstance(plugin.functions(), dict)
        assert isinstance(plugin.classes(), dict)

    def test_the_surfaces_are_stable_across_calls(self):
        """GIVEN this plugin
        WHEN each surface is resolved twice
        THEN the same names map to equal declarations."""
        assert plugin.functions() == plugin.functions()
        assert plugin.classes() == plugin.classes()


class TestDeclaredSurface:
    """What this plugin puts on the table — and that it is fit to be a node type."""

    def test_it_declares_no_function_nodes(self):
        """GIVEN this plugin
        WHEN its function surface is read
        THEN it is empty.

        Asserted rather than left implicit: this is the first plugin whose whole surface is classes,
        so an empty ``functions()`` is a design statement, not an oversight. py-pde's API is
        objects that carry state between steps — a grid, a storage, an equation — and a free function
        would have nothing to hold.
        """
        assert plugin.functions() == {}

    def test_every_declared_class_is_a_class(self):
        """GIVEN this plugin's classes
        WHEN each target is inspected
        THEN it is a class: the host instantiates it for a constructor node."""
        for name, declaration in plugin.classes().items():
            assert isinstance(declaration.target, type), name

    def test_every_declared_port_is_annotated(self):
        """GIVEN this plugin's constructors and declared methods
        WHEN their signatures are read
        THEN no parameter and no return is left bare — the registry is annotation-driven."""
        for class_name, declaration in plugin.classes().items():
            for method_name, method in _declared_members(declaration):
                signature = inspect.signature(method)
                for parameter in signature.parameters.values():
                    if parameter.name == "self":
                        continue
                    assert parameter.annotation is not inspect.Signature.empty, (
                        f"{class_name}.{method_name}:{parameter}"
                    )

    def test_no_declared_port_is_annotated_any(self):
        """GIVEN this plugin's constructors and declared methods
        WHEN their annotations are read
        THEN none of them is ``Any``.

        This is the property the whole surface is designed around. A port annotated ``Any`` makes the
        graph's edge check *skip* that edge, so a mis-wired simulation would only fail once the
        solver had run. Every wrapper here names a concrete type instead, and losing one to ``Any``
        would give that up silently — which is why it is asserted rather than left to review.
        """
        for class_name, declaration in plugin.classes().items():
            for method_name, method in _declared_members(declaration):
                signature = inspect.signature(method)
                annotations = [
                    parameter.annotation
                    for parameter in signature.parameters.values()
                    if parameter.name != "self"
                ]
                if method_name != "__init__":
                    annotations.append(signature.return_annotation)
                assert Any not in annotations, f"{class_name}.{method_name}"

    def test_no_function_name_collides_with_a_class_name(self):
        """GIVEN this plugin's two surfaces
        WHEN their names are compared
        THEN they are disjoint.

        A node type is one string, so a name cannot mean both. ``coral_core`` refuses this when the
        second declaration is made, and the host refuses it again in ``build_port_table``; asserting
        it here keeps the guarantee visible in the plugin that would break it."""
        assert not set(plugin.functions()) & set(plugin.classes())


def _declared_members(declaration):
    """A class's constructor and every method it declares — the callables that become ports.

    Undeclared members are excluded because the registry excludes them:
    ``PyPDEScalarField._holding`` is annotated ``Any`` on purpose and is not a node.
    """
    return [("__init__", declaration.target.__init__)] + [
        (node_type, method.declaration.target) for node_type, method in declaration.methods.items()
    ]
