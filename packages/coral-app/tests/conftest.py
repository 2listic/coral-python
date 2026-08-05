"""Fixtures for the host's own suite.

Two jobs only: hand the designed specimen (``specimen.py``) to the host, and write throwaway graph
files. Nothing here names a plugin, imports one, or needs one installed — the whole point of testing
the host on a specimen is that this directory passes on a bare install, with no skips. That is
enforced from outside, by ``tests/invariants/test_source_rules.py``.
"""

import json
import sys
from pathlib import Path

import pytest

# `--import-mode=importlib` deliberately leaves sys.path alone, so a sibling helper module is not
# importable by name. This directory is added explicitly, which keeps the need local to the package
# that has it: nothing in the workspace root has to know that this suite carries a `specimen.py`.
sys.path.insert(0, str(Path(__file__).parent))

import specimen  # noqa: E402  (needs the sys.path line above)

#: Where the host suite's own graphs live.
GRAPHS = Path(__file__).parent / "graphs"

#: The examples this package ships — the collection graphs, which need no plugin.
EXAMPLES = Path(__file__).parent.parent / "examples"


@pytest.fixture
def specimen_plugins(monkeypatch):
    """Make the specimen plugins loadable by name.

    The host resolves a plugin name through ``coral_app.load``, which reads entry-point metadata.
    The specimen is deliberately not a distribution, so this patches exactly that one lookup —
    name -> ``Plugin`` instance — and nothing else. Everything downstream runs as production code:
    the merge in ``build_function_map`` (including its duplicate-name refusal), the port table, the
    registry renderer, all seven graph checks, and the executor.

    Requested explicitly, never autouse: the tests about ``load`` and ``discover`` themselves must
    see the real ones.
    """

    def load(name: str):
        if name not in specimen.PLUGINS:
            raise LookupError(f"no plugin registered under {name!r} (specimen suite)")
        return specimen.PLUGINS[name]()

    monkeypatch.setattr("coral_app.load", load)


@pytest.fixture(autouse=True)
def isolate_cwd(monkeypatch, tmp_path):
    """Run every test from a disposable working directory.

    ``register`` writes ``node_types.json`` into the current directory, and a graph may write files
    of its own. Pinning cwd to a per-test ``tmp_path`` keeps those artifacts out of the checkout.
    """
    monkeypatch.chdir(tmp_path)


@pytest.fixture
def write_graph(tmp_path):
    """Write a graph dict to a throwaway JSON file and return its path.

    The executor and ``Graph.from_file`` both take a path, so a test that designs a graph inline
    needs somewhere to put it.
    """

    def _write(graph: dict, name: str = "graph.json") -> Path:
        path = tmp_path / name
        path.write_text(json.dumps(graph, indent=2))
        return path

    return _write
