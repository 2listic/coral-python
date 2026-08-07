"""Fixtures for this plugin's suite, and the guard that lets it step aside.

The directory survives ``uv pip uninstall coral-plugin-phiflow``, so it must notice: when the entry point
is absent, ``unit/`` and ``system/`` are dropped from collection, because importing them imports the
plugin. ``test_plugin_present.py`` is deliberately *not* dropped — it imports nothing from the plugin, so
it survives to report a visible skip. Without it, a typo in ``PLUGIN_NAME`` would silently disable this
whole suite and leave the run green.

The shared constants live in ``phiflow_suite.py`` rather than here; see that module's docstring for why.
"""

import json
import sys
from pathlib import Path

import pytest

# `--import-mode=importlib` leaves sys.path alone, so this package's support module is not importable by
# name until its directory is on the path. Kept local to the package that needs it.
sys.path.insert(0, str(Path(__file__).parent))

from phiflow_suite import INSTALLED  # noqa: E402  (needs the sys.path line above)

if not INSTALLED:
    # Not importable, so not collectable. `test_plugin_present.py` stays, and reports the skip.
    collect_ignore_glob = ["unit/*", "system/*"]


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
