"""The host's side of the plugin contract: what it does with a name, and with no names at all.

Everything here runs with **zero plugins installed** and never skips. That is the point: these are
the host's guarantees, not any plugin's, so they are asserted against the designed specimen
(``specimen.py``) or against nothing at all.

What lives elsewhere, on purpose:

* the guarantees that need a *real installed distribution* — that ``discover()`` matches entry-point
  metadata, that importing is lazy, that a real plugin's nodes appear — are in
  ``tests/discovery/test_installed_plugins.py``, which derives its names from ``discover()`` and
  skips cleanly on a bare install;
* whether a *particular* plugin declares a *particular* node is that plugin's own business, tested
  in its own suite.
"""

import pytest
from coral_app import (
    BUILTIN_FUNCTIONS,
    PRIMITIVES_MAP,
    DuplicateNodeTypeError,
    build_class_map,
    build_function_map,
    load,
)
from coral_app.registry import save_registry_to_file
from specimen import BUILTIN_CLASH, CLASS_CLASH, FUNCTION_CLASH, RIVAL, SPECIMEN


class TestLoadFailsLoud:
    """``load`` refuses what it cannot resolve, rather than returning something empty."""

    def test_unknown_name_raises_lookup_error(self):
        """GIVEN no plugin registered under "bogus"
        WHEN load("bogus") is called
        THEN it raises LookupError — a missing plugin is never a silent skip."""
        with pytest.raises(LookupError):
            load("bogus")

    def test_non_plugin_entry_point_raises_type_error(self, monkeypatch):
        """GIVEN an entry point resolving to something that is not a Plugin
        WHEN load() resolves it
        THEN it raises TypeError, naming what it got."""
        from importlib.metadata import EntryPoint

        from coral_app import PLUGIN_GROUP

        # The name is deliberately one no plugin could plausibly be called: the invariants forbid a
        # literal here equal to a plugin name, so a short word like "fake" would turn shipping
        # `plugins/coral-fake` into a failure pointing at this file. See tests/README.md.
        not_a_plugin = EntryPoint(
            name="not-a-real-plugin", value="builtins:int", group=PLUGIN_GROUP
        )
        monkeypatch.setattr("coral_app.entry_points", lambda *a, **k: (not_a_plugin,))

        with pytest.raises(TypeError):
            load("not-a-real-plugin")


class TestBuildMapsFailLoud:
    """``build_*_map`` propagate the unknown-name rule."""

    def test_build_function_map_unknown_name_raises(self):
        """GIVEN an unknown plugin name in the include list
        WHEN build_function_map is called
        THEN it raises LookupError rather than silently skipping."""
        with pytest.raises(LookupError):
            build_function_map(include=["bogus"])

    def test_build_class_map_unknown_name_raises(self):
        """GIVEN an unknown plugin name in the include list
        WHEN build_class_map is called
        THEN it raises LookupError rather than silently skipping."""
        with pytest.raises(LookupError):
            build_class_map(include=["bogus"])


class TestHostWithoutPlugins:
    """The host is a complete program with zero function/class plugins."""

    def test_register_with_no_plugins_emits_only_primitives_and_builtins(self, tmp_path):
        """GIVEN no plugin selected (empty plugin list)
        WHEN the registry is generated
        THEN it contains exactly the host's own two surfaces — the primitive node types and the
             builtin collection functions — and nothing else."""
        out = tmp_path / "node_types.host.json"
        registry = save_registry_to_file(str(out), plugins=[])

        assert set(registry) == set(PRIMITIVES_MAP) | set(BUILTIN_FUNCTIONS)
        assert len(registry) == len(PRIMITIVES_MAP) + len(BUILTIN_FUNCTIONS)
        assert all(entry["node_type"] in ("primitive", "function") for entry in registry.values())

    def test_builtins_are_the_whole_function_map_without_plugins(self):
        """GIVEN no plugin selected
        WHEN the function map is built
        THEN it is exactly the builtins: they need no plugin, and nothing else sneaks in."""
        assert build_function_map(include=[]) == BUILTIN_FUNCTIONS

    def test_no_builtin_classes_without_plugins(self):
        """GIVEN no plugin selected
        WHEN the class map is built
        THEN it is empty: the host owns functions and types, but no classes."""
        assert build_class_map(include=[]) == {}


class TestMerge:
    """Merging the selected plugins: every contribution present, in selection order."""

    def test_every_selected_plugin_contributes(self, specimen_plugins):
        """GIVEN two plugins selected together
        WHEN the maps are built
        THEN both plugins' functions and classes are present."""
        function_map = build_function_map(include=[SPECIMEN, RIVAL])
        class_map = build_class_map(include=[SPECIMEN, RIVAL])

        assert "add_pair" in function_map and "rival_only" in function_map
        assert "Accumulator" in class_map and "Tally" in class_map

    def test_selection_order_is_the_map_order(self, specimen_plugins):
        """GIVEN two plugins selected in a given order
        WHEN the function map is built
        THEN each plugin's names appear in that order, and the host's builtins come last.

        The key order is not cosmetic: ``node_types.json`` is emitted by iterating these maps, so it
        is what the platform reads."""
        names = list(build_function_map(include=[SPECIMEN, RIVAL]))
        reversed_names = list(build_function_map(include=[RIVAL, SPECIMEN]))

        assert names.index("add_pair") < names.index("rival_only")
        assert reversed_names.index("rival_only") < reversed_names.index("add_pair")
        assert names[-len(BUILTIN_FUNCTIONS) :] == list(BUILTIN_FUNCTIONS)

    def test_builtins_are_present_under_every_selection(self, specimen_plugins):
        """GIVEN any plugin selection
        WHEN the function map is built
        THEN each builtin name still resolves to the host's own callable."""
        function_map = build_function_map(include=[SPECIMEN, RIVAL])

        assert all(function_map[name] is func for name, func in BUILTIN_FUNCTIONS.items())


class TestDuplicateNodeTypeIsRefused:
    """One node type, one owner. A second declaration is an error, not a contest.

    A graph names only the node type, so whichever callable had won, the JSON would look identical —
    the graph's meaning would depend on which plugins happen to be installed and in what order. The
    host therefore refuses the selection and names both declarers, which is where the fix belongs.
    """

    def test_two_plugins_declaring_one_function_name(self, specimen_plugins):
        """GIVEN two plugins that both declare `shared_label`
        WHEN they are selected together
        THEN DuplicateNodeTypeError is raised, naming the node type and both plugins."""
        with pytest.raises(DuplicateNodeTypeError) as raised:
            build_function_map(include=[SPECIMEN, FUNCTION_CLASH])

        message = str(raised.value)
        assert "shared_label" in message
        assert SPECIMEN in message and FUNCTION_CLASH in message

    def test_the_error_does_not_depend_on_selection_order(self, specimen_plugins):
        """GIVEN the same two colliding plugins in the opposite order
        WHEN they are selected together
        THEN it is still refused — there is no order in which one legitimately wins."""
        with pytest.raises(DuplicateNodeTypeError):
            build_function_map(include=[FUNCTION_CLASH, SPECIMEN])

    def test_two_plugins_declaring_one_class_name(self, specimen_plugins):
        """GIVEN two plugins that both declare the class `Accumulator`
        WHEN they are selected together
        THEN build_class_map raises too: a class name is a node type as much as a function name."""
        with pytest.raises(DuplicateNodeTypeError, match="Accumulator"):
            build_class_map(include=[SPECIMEN, CLASS_CLASH])

    def test_a_plugin_declaring_a_builtin_name(self, specimen_plugins):
        """GIVEN a plugin declaring a function under the builtin name `list_append`
        WHEN the function map is built with that plugin selected
        THEN DuplicateNodeTypeError is raised — the builtin does not quietly win.

        It could not be selected *with* another plugin either; one is enough, because the other
        declarer is the host itself."""
        with pytest.raises(DuplicateNodeTypeError, match="list_append"):
            build_function_map(include=[BUILTIN_CLASH])

    def test_a_plugin_selected_alone_is_fine(self, specimen_plugins):
        """GIVEN a plugin whose names collide with nothing
        WHEN it is selected alone
        THEN the map is built normally — the rule refuses duplicates, not plugins."""
        assert "shared_label" in build_function_map(include=[SPECIMEN])
