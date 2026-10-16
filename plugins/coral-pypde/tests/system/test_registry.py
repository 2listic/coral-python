"""What this plugin contributes to ``node_types.json``, pinned byte-for-byte.

The **format** is the host's and is pinned in ``coral-app/tests`` against a designed specimen. What
is pinned here is this plugin's **content**: the entries its own classes render to. The split is
deliberate — renaming a format key should show up as one diff in the host's golden, not force an
edit in every plugin package before anyone can see what changed.

To regenerate, from the workspace root::

    uv run coral -p "pypde" register --output=plugins/coral-pypde/tests/system/golden/node_types.pypde.json
"""

import json

import pytest
from coral_app.registry import save_registry_to_file
from coral_plugin_pypde import plugin
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

    def test_every_declared_class_is_a_constructor_or_abstract_node(self, registry):
        """GIVEN this plugin's declared classes
        WHEN the golden is read
        THEN each appears under the class name, as an abstract entry if declared abstract and as
             a constructor node otherwise."""
        for name, declaration in plugin.classes().items():
            expected = "abstract" if declaration.abstract else "constructor"
            assert registry[name]["node_type"] == expected, name

    def test_the_two_base_classes_are_abstract(self, registry):
        """GIVEN the two base classes, which only type sockets
        WHEN the golden is read
        THEN both are abstract entries: neither is a constructor node, which would build an object
             with no `.grid` or `_build_mask`."""
        assert registry["PyPDEGridBase"]["node_type"] == "abstract"
        assert registry["PyPDEShape"]["node_type"] == "abstract"

    def test_a_class_s_method_nodes_are_exactly_its_declared_methods(self, registry):
        """GIVEN this plugin's classes
        WHEN the golden is read
        THEN each class's `Class.*` method entries are exactly the methods it declares: a method
        is a node because it is declared, not because it is public.

        The undeclared side is the point here: ``PyPDEScalarField._holding`` exists so that
        ``solve`` can return a typed field, and it must never become a node a graph could call."""
        for class_name, declaration in plugin.classes().items():
            in_golden = {
                key
                for key, entry in registry.items()
                if entry["node_type"] == "method" and key.startswith(f"{class_name}.")
            }
            assert in_golden == set(declaration.methods), class_name
        assert "PyPDEScalarField._holding" not in registry

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

    def test_a_wrapper_typed_socket_carries_the_wrapper_key(self, registry):
        """GIVEN the solver's ports, annotated with this plugin's own wrapper classes
        WHEN their socket types are read
        THEN each carries its wrapper's class key, and the plain ``int`` port keeps its name.

        Worth pinning because of what follows: the front end can now refuse a grid wired where a
        field belongs, as the host's edge check, which reads the annotations rather than this file,
        already does before the solver starts."""
        arguments = {
            arg["name"]: arg["type"]
            for arg in registry["PyPDEDiffusionPDE.solve"]["arguments"]
            if arg["name"]
        }

        assert arguments["state"] == "PyPDEScalarField"
        assert arguments["storage"] == "PyPDEFileStorage"
        assert arguments["plot"] == "PyPDEPlotTracker"
        assert arguments["t_range"] == "int"

    def test_both_hierarchies_carry_their_bases_and_derived(self, registry):
        """GIVEN the two base classes and their subclasses
        WHEN their golden entries are read
        THEN each subclass lists its base in ``bases``, and each base lists its subclasses in
        ``derived``.

        The front end matches socket types by string, so these two lists are the only place the
        hierarchy reaches it. It does not read them yet: until it does, it refuses a grid or a
        shape where its base is expected, though validation and execution accept one."""
        assert registry["PyPDEUnitGrid"]["bases"] == ["PyPDEGridBase"]
        assert registry["PyPDECartesianGrid"]["bases"] == ["PyPDEGridBase"]
        assert registry["PyPDEGridBase"]["derived"] == ["PyPDEUnitGrid", "PyPDECartesianGrid"]
        assert registry["PyPDECircle"]["bases"] == ["PyPDEShape"]
        assert registry["PyPDERectangle"]["bases"] == ["PyPDEShape"]
        assert registry["PyPDEShape"]["derived"] == ["PyPDECircle", "PyPDERectangle"]

    def test_a_port_annotated_with_a_base_carries_the_base_key(self, registry):
        """GIVEN the ports annotated with one of the two base classes
        WHEN their socket types are read
        THEN each carries the base's key.

        Were the base unregistered, the socket would read ``any`` and the editor would let any wire
        in: registering it is what gives these ports a type in the UI."""
        field = {
            arg["name"]: arg["type"]
            for arg in registry["PyPDEScalarField"]["arguments"]
            if arg["connection_type"] == "input"
        }
        equation = {
            arg["name"]: arg["type"]
            for arg in registry["PyPDEObstacleDiffusionPDE"]["arguments"]
            if arg["connection_type"] == "input"
        }

        assert field["grid"] == "PyPDEGridBase"
        assert [equation[port] for port in ("source", "absorber", "obstacle")] == ["PyPDEShape"] * 3

    def test_the_golden_holds_no_foreign_plugin_entry(self, registry):
        """GIVEN the golden for this plugin alone
        WHEN its keys are compared with what this plugin plus the host declare
        THEN there is nothing else in it.

        Guards against a golden regenerated with the wrong `-p`, which would quietly turn this file
        into a snapshot of somebody else's surface."""
        from coral_app import BUILTINS, PRIMITIVES_MAP

        classes = plugin.classes()
        mine = set(plugin.functions()) | set(classes)
        methods = {
            node_type for declaration in classes.values() for node_type in declaration.methods
        }
        host = set(BUILTINS.functions()) | set(PRIMITIVES_MAP)

        assert set(registry) - mine - methods - host == set()
