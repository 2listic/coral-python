"""Acceptance tests for the plugin discovery/load contract (issue #16, Step 3).

These pin the runtime guarantees the whole modularization rests on. They are written to be
**plugin-set-agnostic**: nothing here asserts a fixed catalog like ``["math", "phiflow", "string"]``,
because that would break the moment someone installs a subset — or an extra third-party plugin. The
mechanics are derived from ``discover()`` and entry-point metadata, so they hold for whatever set is
installed:

* discovery lists installed plugins **without importing** them (laziness);
* ``load`` imports only the requested plugin, and fails loud on an unknown name (``LookupError``,
  D4) or a non-``Plugin`` entry point (``TypeError``);
* the host is a complete program with **zero** function/class plugins (it still emits the
  primitives), and selecting any installed plugin makes exactly its declared nodes appear.

The laziness / no-import assertions run in a **fresh subprocess**: within a single pytest session
other tests have already imported the plugin modules, so ``sys.modules`` here is not a clean slate.
A subprocess gives each check the pristine interpreter the guarantee is actually about.
"""

import subprocess
import sys
import textwrap
from importlib.metadata import EntryPoint, entry_points

import pytest

from coral_app import (
    PLUGIN_GROUP,
    build_class_map,
    build_function_map,
    discover,
    load,
)

#: Plugins installed in this environment (entry-point names, sorted). Derived, never hardcoded.
INSTALLED = discover()

requires_a_plugin = pytest.mark.skipif(not INSTALLED, reason="no plugins installed")
requires_two_plugins = pytest.mark.skipif(
    len(INSTALLED) < 2, reason="laziness check needs at least two installed plugins"
)


def _run_isolated(code: str) -> subprocess.CompletedProcess:
    """Run ``code`` in a fresh interpreter using the same (venv) Python.

    A new process guarantees a clean ``sys.modules`` so import-laziness claims are meaningful,
    unaffected by whatever this pytest session already imported.
    """
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        capture_output=True,
        text=True,
    )


class TestDiscovery:
    """discover() reflects the installed entry points, without importing them."""

    def test_discover_is_sorted_and_unique(self):
        """GIVEN whatever plugins are installed
        WHEN discover() is called
        THEN it returns a sorted list with no duplicates."""
        names = discover()
        assert names == sorted(names)
        assert len(names) == len(set(names))

    def test_discover_matches_entry_point_metadata(self):
        """GIVEN the ``coral.plugins`` entry-point group
        WHEN discover() is called
        THEN it returns exactly the names registered under that group."""
        assert set(discover()) == {ep.name for ep in entry_points(group=PLUGIN_GROUP)}

    def test_discover_does_not_import_plugins(self):
        """GIVEN a pristine interpreter
        WHEN discover() runs
        THEN no plugin's module has been imported as a side effect."""
        result = _run_isolated(
            """
            import sys
            from importlib.metadata import entry_points
            from coral_app import PLUGIN_GROUP, discover
            discover()
            for ep in entry_points(group=PLUGIN_GROUP):
                assert ep.module not in sys.modules, f"discover() imported {ep.module}"
            print("ok")
            """
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "ok"


class TestLoad:
    """load() imports exactly one plugin and fails loud otherwise."""

    @requires_a_plugin
    def test_load_returns_plugin_instance(self):
        """GIVEN any installed plugin
        WHEN load() is called for it
        THEN it returns a live plugin whose surface methods return dicts."""
        plugin = load(INSTALLED[0])
        assert isinstance(plugin.get_functions(), dict)
        assert isinstance(plugin.get_classes(), dict)

    def test_load_unknown_name_raises_lookup_error(self):
        """GIVEN no plugin registered under "bogus"
        WHEN load("bogus") is called
        THEN it raises LookupError (D4: fail-loud, no silent skip)."""
        with pytest.raises(LookupError):
            load("bogus")

    def test_load_non_plugin_entry_point_raises_type_error(self, monkeypatch):
        """GIVEN an entry point resolving to something that is not a Plugin
        WHEN load() resolves it
        THEN it raises TypeError."""
        fake = EntryPoint(name="fake", value="builtins:int", group=PLUGIN_GROUP)
        monkeypatch.setattr("coral_app.entry_points", lambda *a, **k: (fake,))
        with pytest.raises(TypeError):
            load("fake")

    @requires_two_plugins
    def test_load_is_lazy(self):
        """GIVEN a pristine interpreter with at least two plugins installed
        WHEN load() imports one plugin
        THEN no other plugin's module is imported."""
        result = _run_isolated(
            """
            import sys
            from importlib.metadata import entry_points
            from coral_app import PLUGIN_GROUP, discover, load
            modules = {ep.name: ep.module for ep in entry_points(group=PLUGIN_GROUP)}
            target = discover()[0]
            load(target)
            assert modules[target] in sys.modules, f"load({target}) did not import its module"
            for name, mod in modules.items():
                if name != target:
                    assert mod not in sys.modules, f"load({target}) imported {mod}"
            print("ok")
            """
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "ok"


class TestBuildMapsFailLoud:
    """build_*_map propagate the fail-loud unknown-name rule (D4)."""

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
    """The host is a complete program even with zero function/class plugins."""

    def test_register_with_no_plugins_emits_only_primitives(self, tmp_path):
        """GIVEN no plugin selected (empty module list)
        WHEN the registry is generated
        THEN it contains exactly the six primitive node types."""
        from coral_app import PRIMITIVES_MAP
        from coral_app.registry import save_registry_to_file

        out = tmp_path / "node_types.host.json"
        registry = save_registry_to_file(str(out), modules=[])

        assert set(registry) == set(PRIMITIVES_MAP)
        assert len(registry) == 6
        assert all(entry["node_type"] == "primitive" for entry in registry.values())


class TestPluginAddsNodes:
    """Selecting any installed plugin makes exactly its declared nodes appear."""

    @requires_a_plugin
    @pytest.mark.parametrize("name", INSTALLED)
    def test_selected_plugin_contributes_its_nodes(self, name, tmp_path):
        """GIVEN an installed plugin selected on its own
        WHEN the registry is generated for it
        THEN every function it declares appears as a function node and every class as a
             constructor node."""
        from coral_app.registry import save_registry_to_file

        plugin = load(name)
        out = tmp_path / f"node_types.{name}.json"
        registry = save_registry_to_file(str(out), modules=[name])

        for func_name in plugin.get_functions():
            assert registry[func_name]["node_type"] == "function"
        for class_name in plugin.get_classes():
            assert registry[class_name]["node_type"] == "constructor"
