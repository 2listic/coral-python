"""What this plugin contributes to ``node_types.json``, pinned byte-for-byte.

The **format** is the host's and is pinned in ``coral-app/tests`` against a designed specimen. What
is pinned here is this plugin's **content**: the entries its own classes render to. The split is
deliberate — renaming a format key should show up as one diff in the host's golden, not force an
edit in every plugin package before anyone can see what changed.

To regenerate, from the workspace root::

    uv run coral -p "pypde" register --output=plugins/coral-pypde/tests/system/golden/node_types.pypde.json
"""

import inspect
import json

import pytest
from coral_app.registry import save_registry_to_file
from coral_plugin_pypde import PyPDEPlugin
from pypde_suite import GOLDEN, PLUGIN_NAME


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

        Bytes, not parsed content: key order is part of the file the platform reads, and a
        reordering would be a change to the artifact we hand over even if every entry survived."""
        assert GOLDEN.exists(), f"missing golden: {GOLDEN}"

        out = tmp_path / GOLDEN.name
        save_registry_to_file(str(out), plugins=[PLUGIN_NAME])

        assert out.read_bytes() == GOLDEN.read_bytes(), (
            f"registry for {PLUGIN_NAME!r} diverged from {GOLDEN.name}; regenerate only on purpose"
        )


class TestTheGoldenDescribesThisPlugin:
    """The golden is only a guard if it really covers what this plugin declares."""

    def test_every_declared_class_is_a_constructor_node(self, registry):
        """GIVEN this plugin's declared classes
        WHEN the golden is read
        THEN each appears as a constructor node under the class name."""
        for name in PyPDEPlugin().get_classes():
            assert registry[name]["node_type"] == "constructor", name

    def test_every_public_method_is_a_method_node_and_no_private_one_is(self, registry):
        """GIVEN this plugin's classes
        WHEN the golden is read
        THEN each public method is present as `Class.method`, and no private one is.

        The private half is the point here: ``PyPDEScalarField._holding`` exists so that ``solve``
        can return a typed field, and it must never become a node a graph could call."""
        for class_name, cls in PyPDEPlugin().get_classes().items():
            for member in dir(cls):
                if not inspect.isfunction(getattr(cls, member)):
                    continue
                key = f"{class_name}.{member}"
                if member.startswith("_"):
                    assert key not in registry
                else:
                    assert registry[key]["node_type"] == "method", key

    def test_solve_declares_five_inputs_and_one_output(self, registry):
        """GIVEN the solver's method node
        WHEN its golden entry is read
        THEN it has five input ports in order and a single output.

        Port 0 is the instance; the two tracker ports are 3 and 4, which is the shape the decision
        to give each tracker its own port produces — a single `list` port would show four inputs."""
        entry = registry["PyPDEDiffusionPDE.solve"]
        names = [arg["name"] for arg in entry["arguments"] if arg["connection_type"] == "input"]

        assert names == ["self", "state", "t_range", "storage", "plot"]
        assert entry["outputs"] == [5]

    def test_a_wrapper_typed_socket_renders_any(self, registry):
        """GIVEN the solver's ports, annotated with this plugin's own wrapper classes
        WHEN their socket types are read
        THEN they are ``any``, while the plain ``int`` port keeps its name.

        Neither a defect in this plugin nor something it can fix: the registry's type table knows the
        six primitives and the three collection names, and every other class falls through to
        ``any``. Worth pinning because of what follows — the editor cannot refuse a grid wired where
        a field belongs, while the host's edge check, which reads the annotations rather than this
        file, refuses it before the solver starts."""
        arguments = {
            arg["name"]: arg["type"]
            for arg in registry["PyPDEDiffusionPDE.solve"]["arguments"]
            if arg["name"]
        }

        assert arguments["state"] == "any"
        assert arguments["storage"] == "any"
        assert arguments["plot"] == "any"
        assert arguments["t_range"] == "int"

    def test_the_golden_holds_no_foreign_plugin_entry(self, registry):
        """GIVEN the golden for this plugin alone
        WHEN its keys are compared with what this plugin plus the host declare
        THEN there is nothing else in it.

        Guards against a golden regenerated with the wrong `-p`, which would quietly turn this file
        into a snapshot of somebody else's surface."""
        from coral_app import BUILTIN_FUNCTIONS, PRIMITIVES_MAP

        plugin = PyPDEPlugin()
        mine = set(plugin.get_functions()) | set(plugin.get_classes())
        methods = {key for key in registry if key.split(".")[0] in plugin.get_classes()}
        host = set(BUILTIN_FUNCTIONS) | set(PRIMITIVES_MAP)

        assert set(registry) - mine - methods - host == set()
