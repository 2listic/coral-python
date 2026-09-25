"""Fixtures for this plugin's suite, and the guard that lets it step aside.

The directory survives ``uv pip uninstall coral-plugin-string``, so it must notice: when the entry point
is absent, everything that would import the plugin is dropped from collection: ``system/`` entire, and
every module in ``unit/`` but one. ``unit/test_plugin_present.py`` imports nothing from the plugin, so
it survives to report a visible skip. Without it, a typo in ``PLUGIN_NAME`` would silently disable this
whole suite and leave the run green.

The shared constants live in ``string_suite.py`` rather than here; see that module's docstring for why.
"""

import json
import sys
from pathlib import Path

import pytest

# `--import-mode=importlib` leaves sys.path alone, so this package's support module is not importable by
# name until its directory is on the path. Kept local to the package that needs it.
sys.path.insert(0, str(Path(__file__).parent))

from string_suite import INSTALLED  # noqa: E402  (needs the sys.path line above)

if not INSTALLED:
    # Not importable, so not collectable. The presence report imports nothing from the plugin, so it
    # stays and reports the skip; listing the rest by scan keeps a new unit module covered by default.
    collect_ignore_glob = ["system/*"]
    collect_ignore = [
        f"unit/{path.name}"
        for path in (Path(__file__).parent / "unit").glob("test_*.py")
        if path.name != "test_plugin_present.py"
    ]


@pytest.fixture(autouse=True)
def isolate_cwd(monkeypatch, tmp_path):
    """Run every test from a disposable working directory.

    A graph may write files relative to the current directory, and ``register`` writes
    ``node_types.json`` into it. Keep all of that out of the checkout.
    """
    monkeypatch.chdir(tmp_path)


@pytest.fixture
def write_graph(tmp_path):
    """Write a graph dict to a throwaway JSON file and return its path."""

    def _write(graph: dict, filename: str = "graph.json") -> Path:
        path = tmp_path / filename
        path.write_text(json.dumps(graph, indent=2))
        return path

    return _write
