"""What this plugin contributes to ``node_types.json``, pinned byte-for-byte.

The **format** is the host's and is pinned in ``coral-app/tests`` against a designed
specimen. What is pinned here is this plugin's **content**: the entries its own functions and classes
render to. The split is deliberate — renaming a format key should show up as one diff in the host's
golden, not force an edit in three plugin packages before anyone can see what changed.

The golden was recorded from the pre-modularization flat code and has survived every refactor since,
which is exactly its value. Regenerating it is a reviewable act: an intentional change to this
plugin's surface produces a diff someone has to look at.

To regenerate, from the workspace root::

    uv run coral -p "phiflow" register --output=plugins/coral-phiflow/tests/system/golden/node_types.phiflow.json
"""

import inspect
import json

import pytest
from coral_app.registry import save_registry_to_file
from coral_plugin_phiflow import PhiFlowPlugin
from phiflow_suite import GOLDEN, PLUGIN_NAME


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
        for name in PhiFlowPlugin().get_functions():
            assert registry[name]["node_type"] == "function", name

    def test_every_declared_class_is_a_constructor_node(self, registry):
        """GIVEN this plugin's declared classes
        WHEN the golden is read
        THEN each appears as a constructor node under the class name."""
        for name in PhiFlowPlugin().get_classes():
            assert registry[name]["node_type"] == "constructor", name

    def test_every_public_method_is_a_method_node(self, registry):
        """GIVEN this plugin's classes
        WHEN the golden is read
        THEN each public method is present as `Class.method`, and no private one is."""
        for class_name, cls in PhiFlowPlugin().get_classes().items():
            for member in dir(cls):
                if not inspect.isfunction(getattr(cls, member)):
                    continue
                key = f"{class_name}.{member}"
                if member.startswith("_"):
                    assert key not in registry
                else:
                    assert registry[key]["node_type"] == "method", key

    def test_the_iterate_node_declares_three_outputs(self, registry):
        """GIVEN `phiflow_iterate`, annotated `Tuple[Any, Any, Any]`
        WHEN its golden entry is read
        THEN it declares three output ports, each `any`.

        Both halves matter: three ports is what lets a graph select the smoke trajectory with
        `source_output`, and `any` is why no edge leaving this node can be checked before the
        simulation runs."""
        entry = registry["phiflow_iterate"]
        outputs = [arg for arg in entry["arguments"] if arg["connection_type"] == "output"]

        assert len(entry["outputs"]) == 3
        assert [arg["type"] for arg in outputs] == ["any", "any", "any"]

    def test_the_grid_constructors_take_a_domain_and_two_resolutions(self, registry):
        """GIVEN the two grid wrappers
        WHEN their constructor entries are read
        THEN each takes three inputs in port order: the domain, then the x and y resolutions."""
        for key in ("PhiFlowStaggeredGrid", "PhiFlowCenteredGrid"):
            names = [arg["name"] for arg in registry[key]["arguments"]]
            assert names == ["domain_box", "resolution_x", "resolution_y"], key

    def test_the_geometry_getters_are_method_nodes(self, registry):
        """GIVEN the getter on each geometry wrapper
        WHEN the golden is read
        THEN each is a method node — this is how a graph unwraps a geometry when it needs the raw one."""
        for key in ("PhiFlowBox.get_box", "PhiFlowSphere.get_sphere", "PhiFlowCuboid.get_cuboid"):
            assert registry[key]["node_type"] == "method", key

    def test_the_golden_holds_no_foreign_plugin_entry(self, registry):
        """GIVEN the golden for this plugin alone
        WHEN its keys are compared with what this plugin plus the host declare
        THEN there is nothing else in it.

        Guards against a golden regenerated with the wrong `-p`, which would quietly turn this file
        into a snapshot of somebody else's surface."""
        from coral_app import BUILTIN_FUNCTIONS, PRIMITIVES_MAP

        plugin = PhiFlowPlugin()
        mine = set(plugin.get_functions()) | set(plugin.get_classes())
        methods = {key for key in registry if key.split(".")[0] in plugin.get_classes()}
        host = set(BUILTIN_FUNCTIONS) | set(PRIMITIVES_MAP)

        assert set(registry) - mine - methods - host == set()
