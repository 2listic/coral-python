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

from abc import ABC, abstractmethod

import pytest
from coral_app import (
    BUILTINS,
    PRIMITIVES_MAP,
    DuplicateNodeTypeError,
    build_class_map,
    build_function_map,
    load,
)
from coral_app.registry import save_registry_to_file
from coral_core import Plugin
from specimen import BUILTIN_CLASH, CLASS_CLASH, FUNCTION_CLASH, HIERARCHY_CLASH, RIVAL, SPECIMEN


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


class TestLoadResolves:
    """What ``load`` returns, for each kind of entry point a plugin may declare."""

    @staticmethod
    def resolving_to(monkeypatch, target):
        """Make the one entry point ``load`` finds resolve to ``target``."""

        class EntryPointStub:
            def load(self):
                return target

        monkeypatch.setattr("coral_app.entry_points", lambda *a, **k: (EntryPointStub(),))

    def test_a_plugin_instance_is_returned_as_is(self, monkeypatch):
        """GIVEN an entry point resolving to a Plugin instance
        WHEN load() resolves it
        THEN that very instance is returned: its declarations live on it."""
        plugin = Plugin()
        self.resolving_to(monkeypatch, plugin)

        assert load("not-a-real-plugin") is plugin

    def test_a_plugin_subclass_is_refused(self, monkeypatch):
        """GIVEN an entry point resolving to a Plugin subclass rather than an instance
        WHEN load() resolves it
        THEN it raises TypeError: a plugin is the instance its node types are declared on."""

        class Subclassing(Plugin):
            pass

        self.resolving_to(monkeypatch, Subclassing)

        with pytest.raises(TypeError, match="not a coral_core.Plugin instance"):
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

        assert set(registry) == set(PRIMITIVES_MAP) | set(BUILTINS.functions())
        assert len(registry) == len(PRIMITIVES_MAP) + len(BUILTINS.functions())
        assert all(entry["node_type"] in ("primitive", "function") for entry in registry.values())

    def test_builtins_are_the_whole_function_map_without_plugins(self):
        """GIVEN no plugin selected
        WHEN the function map is built
        THEN it is exactly the builtins: they need no plugin, and nothing else sneaks in."""
        assert build_function_map(include=[]) == BUILTINS.functions()

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
        builtins = list(BUILTINS.functions())
        assert names[-len(builtins) :] == builtins

    def test_builtins_are_present_under_every_selection(self, specimen_plugins):
        """GIVEN any plugin selection
        WHEN the function map is built
        THEN each builtin name still resolves to the host's own declaration."""
        function_map = build_function_map(include=[SPECIMEN, RIVAL])

        assert all(function_map[name] == decl for name, decl in BUILTINS.functions().items())


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


class TestPluginsDoNotShareAHierarchy:
    """A class registered by one plugin may not derive from a class registered by another: the
    override rules are checked within one plugin's declarations, so across plugins nothing would."""

    @pytest.mark.parametrize(
        "selection",
        [[SPECIMEN, HIERARCHY_CLASH], [HIERARCHY_CLASH, SPECIMEN]],
        ids=["base-first", "subclass-first"],
    )
    def test_a_subclass_of_another_plugin_s_class_is_refused(self, specimen_plugins, selection):
        """GIVEN a plugin registering a subclass of a class the specimen registers
        WHEN the class map is built with both selected, in either order
        THEN a plain ValueError names both classes and both plugins: no name is declared twice,
             so it is not a DuplicateNodeTypeError."""
        with pytest.raises(
            ValueError,
            match=r"class 'Audited' of plugin 'hierarchy-clash' derives from class 'Accumulator' "
            r"of plugin 'specimen'",
        ) as raised:
            build_class_map(include=selection)

        assert type(raised.value) is ValueError

    def test_the_subclass_s_plugin_selected_alone_is_fine(self, specimen_plugins):
        """GIVEN the same plugin, selected without the one registering the base
        WHEN the class map is built
        THEN no error: an unregistered base is shared with no plugin."""
        assert list(build_class_map(include=[HIERARCHY_CLASH])) == ["Audited"]

    @pytest.mark.parametrize(
        "selection, message",
        [
            (["first", "second"], r"as 'Base' by plugin 'first' and as 'Other' by plugin 'second'"),
            (["second", "first"], r"as 'Other' by plugin 'second' and as 'Base' by plugin 'first'"),
        ],
        ids=["in-order", "reversed"],
    )
    def test_one_class_under_two_keys_is_a_duplicate(self, monkeypatch, selection, message):
        """GIVEN two plugins registering one class under two keys, one also registering a subclass
        WHEN the class map is built with both selected, in either order
        THEN DuplicateNodeTypeError naming the class, both keys and both plugins: the subclass's
             base is one both plugins hold, so a shared-hierarchy message would mislead."""

        class Base:
            def __init__(self, size: int): ...

        class Child(Base): ...

        first, second = Plugin(), Plugin()
        first.cls(Base)
        first.cls(Child)
        second.cls(Base, name="Other")
        monkeypatch.setattr("coral_app.load", {"first": first, "second": second}.__getitem__)

        with pytest.raises(DuplicateNodeTypeError, match=r"class 'Base' is registered " + message):
            build_class_map(include=selection)


class TestAVirtualSubclassIsUnrelated:
    """A class's bases are decided by inheritance: ABC registration, or a ``__subclasshook__``,
    relates no registered class to another, so it refuses nothing at load. An instance of a virtual
    subclass is refused by the abstract class's methods instead."""

    @pytest.mark.parametrize("hook", [False, True], ids=["register", "subclasshook"])
    def test_a_virtual_subclass_across_plugins_loads(self, monkeypatch, hook):
        """GIVEN one plugin registering an abstract class, another a class that is its virtual
             subclass, by ABC registration or by the abstract class's __subclasshook__
        WHEN the class map is built with both selected
        THEN both are registered: neither is a base of the other."""
        meters, gauges = Plugin(), Plugin()

        @meters.cls
        class Meter(ABC):
            @classmethod
            def __subclasshook__(cls, other):
                return True if hook and hasattr(other, "read") else NotImplemented

            @meters.method(const=True)
            @abstractmethod
            def read(self) -> float: ...

        @gauges.cls
        class Gauge:
            def read(self) -> float:
                return 1.0

        if not hook:
            Meter.register(Gauge)
        monkeypatch.setattr("coral_app.load", {"meters": meters, "gauges": gauges}.__getitem__)

        assert list(build_class_map(include=["meters", "gauges"])) == ["Meter", "Gauge"]
