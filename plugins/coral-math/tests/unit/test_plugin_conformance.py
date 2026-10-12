"""This plugin's conformance to the ``coral_core.Plugin`` contract.

Every plugin asserts this for itself. How a ``Plugin`` declares and resolves node types belongs to
``coral-core`` and is tested there; what belongs here is that **this** plugin is one, and that what
it declares is coherent: annotated callables, nothing accidentally declared twice.

Nothing here imports ``coral_app``. Conformance is a fact about the plugin and the contract, and needs
no host.
"""

import inspect

from coral_core import Plugin
from coral_plugin_math import plugin


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
        THEN the same names map to equal declarations.

        The host may build a map more than once per process (`register` then `run`), and the class
        surface is resolved anew on every call."""
        assert plugin.functions() == plugin.functions()
        assert plugin.classes() == plugin.classes()


class TestDeclaredSurface:
    """What this plugin puts on the table — and that it is fit to be a node type."""

    def test_every_declared_function_is_callable(self):
        """GIVEN this plugin's functions
        WHEN each target is inspected
        THEN it is callable — the host will call it with no further ceremony."""
        for name, declaration in plugin.functions().items():
            assert callable(declaration.target), name

    def test_every_declared_class_is_a_class(self):
        """GIVEN this plugin's classes
        WHEN each target is inspected
        THEN it is a class: the host instantiates it for a constructor node."""
        for name, declaration in plugin.classes().items():
            assert isinstance(declaration.target, type), name

    def test_every_function_parameter_is_annotated(self):
        """GIVEN this plugin's functions
        WHEN their signatures are read together with their declared ``annotations=``
        THEN every parameter and every return is typed by one or the other.

        This is the bargain the host's registry and graph checks rest on: an unannotated port renders
        as `any` and makes the edge check *skip*, so a wrong wire is only found when the graph runs.
        Whether that happens is the plugin author's choice, and this plugin's choice is to annotate.
        """
        for name, declaration in plugin.functions().items():
            bare = _bare(declaration.target, declaration.annotations, with_return=True)
            assert bare == [], f"{name}: {bare}"

    def test_every_declared_method_is_annotated(self):
        """GIVEN this plugin's classes
        WHEN their declared methods and constructors are read with their ``annotations=``
        THEN every parameter, and every method's return, is typed, for the same reason as the
             functions; a constructor's output is the instance, so it has no return to type."""
        for class_name, declaration in plugin.classes().items():
            bare = _bare(declaration.target, declaration.annotations, with_return=False)
            assert bare == [], f"{class_name}: {bare}"
            for node_type, method in declaration.methods.items():
                method_declaration = method.declaration
                bare = _bare(
                    method_declaration.target, method_declaration.annotations, with_return=True
                )
                assert bare == [], f"{node_type}: {bare}"

    def test_no_function_name_collides_with_a_class_name(self):
        """GIVEN this plugin's two surfaces
        WHEN their names are compared
        THEN they are disjoint.

        A node type is one string, so a name cannot mean both. ``coral_core`` refuses this when the
        second declaration is made, and the host refuses it again in ``build_port_table``; asserting
        it here keeps the guarantee visible in the plugin that would break it."""
        assert not set(plugin.functions()) & set(plugin.classes())


def _bare(target, annotations, *, with_return):
    """The parameters of ``target`` — and its return, if ``with_return`` — that neither its
    signature nor its declared ``annotations=`` types.

    ``self`` is never bare: it is port 0, typed by its class. A class's signature is its
    constructor's, which already omits ``self``.
    """
    signature = inspect.signature(target)
    bare = [
        parameter.name
        for parameter in signature.parameters.values()
        if parameter.name != "self"
        and parameter.annotation is inspect.Parameter.empty
        and parameter.name not in annotations
    ]
    if (
        with_return
        and signature.return_annotation is inspect.Signature.empty
        and "return" not in annotations
    ):
        bare.append("return")
    return bare
