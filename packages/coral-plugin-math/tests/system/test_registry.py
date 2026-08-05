"""What this plugin contributes to ``node_types.json``, pinned byte-for-byte.

The **format** is the host's and is pinned in ``packages/coral-app/tests`` against a designed
specimen. What is pinned here is this plugin's **content**: the entries its own functions and classes
render to. The split is deliberate — renaming a format key should show up as one diff in the host's
golden, not force an edit in three plugin packages before anyone can see what changed.

The golden was recorded from the pre-modularization flat code and has survived every refactor since,
which is exactly its value. Regenerating it is a reviewable act: an intentional change to this
plugin's surface produces a diff someone has to look at.

To regenerate, from the workspace root::

    uv run coral -p "math" register --output=packages/coral-plugin-math/tests/system/golden/node_types.math.json
"""

import inspect
import json

import pytest
from coral_app.registry import save_registry_to_file
from coral_plugin_math import MathPlugin
from math_suite import GOLDEN, PLUGIN_NAME


@pytest.fixture(scope="module")
def registry():
    """The recorded golden, parsed."""
    return json.loads(GOLDEN.read_text())


class TestGolden:
    """Byte equality with the recorded registry for this plugin alone."""

    def test_the_registry_matches_the_golden_bytes(self, tmp_path):
        """GIVEN the recorded golden for this plugin
        WHEN `register` regenerates the registry with only this plugin selected
        THEN the emitted file is byte-for-byte identical.

        Bytes, not parsed content: key order is part of the file the platform reads, and a reordering
        would be a change to the artifact we hand over even if every entry survived."""
        assert GOLDEN.exists(), f"missing golden: {GOLDEN}"

        out = tmp_path / GOLDEN.name
        save_registry_to_file(str(out), plugins=[PLUGIN_NAME])

        assert out.read_bytes() == GOLDEN.read_bytes(), (
            f"registry for {PLUGIN_NAME!r} diverged from {GOLDEN.name}; regenerate only on purpose"
        )


class TestTheGoldenDescribesThisPlugin:
    """The golden is only a guard if it really covers what this plugin declares."""

    def test_every_declared_function_is_a_function_node(self, registry):
        """GIVEN this plugin's declared functions
        WHEN the golden is read
        THEN each appears as a function node under its own name."""
        for name in MathPlugin().get_functions():
            assert registry[name]["node_type"] == "function", name

    def test_every_declared_class_is_a_constructor_node(self, registry):
        """GIVEN this plugin's declared classes
        WHEN the golden is read
        THEN each appears as a constructor node under the class name."""
        for name in MathPlugin().get_classes():
            assert registry[name]["node_type"] == "constructor", name

    def test_every_public_method_is_a_method_node(self, registry):
        """GIVEN this plugin's classes
        WHEN the golden is read
        THEN each public method is present as `Class.method`, and no private one is."""
        for class_name, cls in MathPlugin().get_classes().items():
            for member in dir(cls):
                if not inspect.isfunction(getattr(cls, member)):
                    continue
                key = f"{class_name}.{member}"
                if member.startswith("_"):
                    assert key not in registry
                else:
                    assert registry[key]["node_type"] == "method", key

    def test_the_dotted_function_names_stay_functions(self, registry):
        """GIVEN this plugin's `math.*` wrappers, whose names contain a dot
        WHEN the golden is read
        THEN they are function nodes, not methods of a class called `math`.

        The dot is part of the node type string the platform stores in a graph, so this is a contract
        detail, not a naming preference."""
        for name in ("math.sqrt", "math.sin", "math.cos", "math.pow"):
            assert registry[name]["node_type"] == "function"
            assert registry[name]["type"] == name

    def test_the_sockets_carry_real_types_not_any(self, registry):
        """GIVEN this plugin's annotated functions
        WHEN their argument types are read from the golden
        THEN none is 'any'.

        This plugin annotates everything, so every one of its edges is checkable by the graph before
        execution. A plugin that wrote `Any` would still work, but its wiring errors would only
        surface at run time — the trade is the author's, and this records which side this plugin is on.
        """
        for name in MathPlugin().get_functions():
            types = [argument["type"] for argument in registry[name]["arguments"]]
            assert "any" not in types, f"{name}: {types}"

    def test_the_multi_output_function_declares_three_outputs(self, registry):
        """GIVEN `test_tuple_return`, annotated `Tuple[float, float, float]`
        WHEN its golden entry is read
        THEN it declares three output ports, each a float — which is what lets a graph select one
             with `source_output`."""
        entry = registry["test_tuple_return"]

        assert len(entry["outputs"]) == 3
        outputs = [arg for arg in entry["arguments"] if arg["connection_type"] == "output"]
        assert [arg["type"] for arg in outputs] == ["float", "float", "float"]

    def test_print_number_declares_no_output(self, registry):
        """GIVEN `print_number`, which returns None
        WHEN its golden entry is read
        THEN it has no outputs at all, so the editor offers nothing to wire onward."""
        assert registry["print_number"]["outputs"] == []

    def test_the_golden_holds_no_foreign_plugin_entry(self, registry):
        """GIVEN the golden for this plugin alone
        WHEN its keys are compared with what this plugin plus the host declare
        THEN there is nothing else in it.

        Guards against a golden regenerated with the wrong `-p`, which would quietly turn this file
        into a snapshot of somebody else's surface."""
        from coral_app import BUILTIN_FUNCTIONS, PRIMITIVES_MAP

        plugin = MathPlugin()
        mine = set(plugin.get_functions()) | set(plugin.get_classes())
        methods = {key for key in registry if key.split(".")[0] in plugin.get_classes()}
        host = set(BUILTIN_FUNCTIONS) | set(PRIMITIVES_MAP)

        assert set(registry) - mine - methods - host == set()
