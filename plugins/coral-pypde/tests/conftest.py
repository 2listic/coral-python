"""Fixtures for this plugin's suite, and the guard that lets it step aside.

The directory survives ``uv pip uninstall coral-plugin-pypde``, so it must notice: when the entry
point is absent, everything that would import the plugin is dropped from collection — ``system/``
entire, and every module in ``unit/`` but one. ``unit/test_plugin_present.py`` imports nothing from
the plugin, so it survives to report a visible skip. Without it, a typo in ``PLUGIN_NAME`` would
silently disable this whole suite and leave the run green.

The shared constants live in ``pypde_suite.py``; see that module's docstring for why.
"""

import sys
from pathlib import Path

import pytest

# `--import-mode=importlib` leaves sys.path alone, so this package's support module is not
# importable by name until its directory is on the path. Kept local to the package that needs it.
sys.path.insert(0, str(Path(__file__).parent))

from pypde_suite import INSTALLED  # noqa: E402  (needs the sys.path line above)

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

    This plugin's graph writes an HDF5 file and a movie relative to the current directory, and
    ``register`` writes ``node_types.json`` into it. Keep all of that out of the checkout.
    """
    monkeypatch.chdir(tmp_path)
