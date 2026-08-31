"""Tests for the CLI's own contract with the platform (issue #30).

The platform drives this backend through the ``coral`` console script, so what the *CLI* defaults to
is part of the contract — and the C++ backend has no "write nothing" mode: it defaults ``--touch-dir``
to ``"./"`` and touches unconditionally. That default is the one thing only a CLI-level test can
pin, since ``WorkflowExecutor(touch_dir=None)`` deliberately writes nothing.
"""

import json

import pytest
from coral_app.cli import DEFAULT_TOUCH_DIR, main
from coral_app.nodestatus import RUNNING, STATUS_SUFFIXES, SUCCEEDED

# Builtin collection nodes only, so the graph itself needs no plugin.
GRAPH = {
    "workflow": {
        "nodes": {
            "0": {"type": "list_new"},
            "1": {"type": "int", "value": 7},
            "2": {"type": "list_append"},
        },
        "edges": {
            "e0": {"source": "0", "target": "2", "source_output": 0, "target_input": 0},
            "e1": {"source": "1", "target": "2", "source_output": 0, "target_input": 1},
        },
    }
}


@pytest.fixture
def graph_file(tmp_path):
    """Write the builtin-only graph into the (already isolated) working directory."""
    path = tmp_path / "graph.json"
    path.write_text(json.dumps(GRAPH))
    return path


class TestRunTouchDir:
    """``coral run`` and the per-node status markers."""

    def test_the_default_is_the_cwd(self):
        """GIVEN the CLI module
        WHEN its touch-dir default is read
        THEN it is ``"./"``, as in the C++ backend — the flag being omitted does not mean silence."""
        assert DEFAULT_TOUCH_DIR == "./"

    @pytest.mark.math
    def test_run_without_the_flag_writes_markers_into_the_cwd(
        self, graph_file, tmp_path, monkeypatch
    ):
        """GIVEN ``coral run <graph>`` with no ``--touch-dir``
        WHEN it executes
        THEN the markers land in the current directory, two per node, and the graph file is left
        alone. This is the C++-faithful default, and the platform relies on it: it runs the backend
        inside the job directory it then watches."""
        monkeypatch.setattr("sys.argv", ["coral", "-p", "math", "run", str(graph_file)])

        main()

        markers = sorted(
            path.name for path in tmp_path.iterdir() if path.name.endswith(STATUS_SUFFIXES)
        )
        assert markers == [
            f"0_auto_0{RUNNING}",
            f"0_auto_0{SUCCEEDED}",
            f"1_auto_1{RUNNING}",
            f"1_auto_1{SUCCEEDED}",
            f"2_auto_2{RUNNING}",
            f"2_auto_2{SUCCEEDED}",
        ]
        assert graph_file.exists()

    @pytest.mark.math
    def test_the_flag_redirects_the_markers(self, graph_file, tmp_path, monkeypatch):
        """GIVEN ``coral run <graph> --touch-dir <dir>`` naming a directory that does not exist
        WHEN it executes
        THEN the directory is created, the markers go there, and none is left in the cwd."""
        target = tmp_path / "job-1" / "status"
        monkeypatch.setattr(
            "sys.argv",
            ["coral", "-p", "math", "run", str(graph_file), "--touch-dir", str(target)],
        )

        main()

        assert len([path for path in target.iterdir() if path.name.endswith(STATUS_SUFFIXES)]) == 6
        assert not [path for path in tmp_path.iterdir() if path.name.endswith(STATUS_SUFFIXES)]
