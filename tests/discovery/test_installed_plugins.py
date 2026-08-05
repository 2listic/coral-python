"""The guarantees that need a **real installed distribution**.

Repo-level, because they name no plugin: every name is derived from ``discover()`` and from
entry-point metadata, so the file holds for whatever set happens to be installed — the fully synced
workspace, a subset, or an extra third-party plugin. On a bare install (no ``coral-plugin-*`` at all)
the plugin-dependent cases skip cleanly, which is correct: there is no distribution to make a claim
about.

What is *not* here: anything the host guarantees on its own. Discovery's fail-loud rules, the
zero-plugin host, the merge and its duplicate-name refusal are all in
``packages/coral-app/tests/test_discovery.py``, tested against the designed specimen so they run with
no plugin installed and never skip.

The laziness / no-import assertions run in a **fresh subprocess**: within a single pytest session
other tests have already imported the plugin modules, so ``sys.modules`` here is not a clean slate.
A subprocess gives each check the pristine interpreter the guarantee is actually about.
"""

import subprocess
import sys
import textwrap
from importlib.metadata import entry_points

import pytest
from coral_app import PLUGIN_GROUP, build_class_map, build_function_map, discover, load

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
    """load() resolves a real entry point to a live plugin, and imports only that one."""

    @requires_a_plugin
    def test_load_returns_plugin_instance(self):
        """GIVEN any installed plugin
        WHEN load() is called for it
        THEN it returns a live plugin whose surface methods return dicts."""
        plugin = load(INSTALLED[0])
        assert isinstance(plugin.get_functions(), dict)
        assert isinstance(plugin.get_classes(), dict)

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
            ep_modules = {ep.name: ep.module for ep in entry_points(group=PLUGIN_GROUP)}
            target = discover()[0]
            load(target)
            assert ep_modules[target] in sys.modules, f"load({target}) did not import its module"
            for name, mod in ep_modules.items():
                if name != target:
                    assert mod not in sys.modules, f"load({target}) imported {mod}"
            print("ok")
            """
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "ok"


class TestInstalledPluginsAgree:
    """The installed set must be usable *together* — the state an empty ``-p`` puts it in."""

    @requires_a_plugin
    def test_all_installed_plugins_declare_no_duplicate_node_type(self):
        """GIVEN every installed plugin, which is what an empty `-p` resolves to
        WHEN the function and class maps are built for all of them at once
        THEN the maps are built — no DuplicateNodeTypeError.

        The rule itself is the host's and is tested on the specimen; this is the deployment question
        it raises. Math and string both declared ``print_result`` until issue #27, so with every
        plugin selected the platform silently received only one of the two; today that state would
        make the default ``coral register`` fail for every user, which is the point of the rule.
        """
        function_map = build_function_map()
        class_map = build_class_map()

        assert set(function_map)
        assert isinstance(class_map, dict)


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
        registry = save_registry_to_file(str(out), plugins=[name])

        for func_name in plugin.get_functions():
            assert registry[func_name]["node_type"] == "function"
        for class_name in plugin.get_classes():
            assert registry[class_name]["node_type"] == "constructor"
