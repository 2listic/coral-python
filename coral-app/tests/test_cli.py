"""The CLI's own contract with the platform — ``coral_app.cli``.

The platform drives this backend through the ``coral`` console script, so what the *CLI* defaults to
is part of the contract — and the reference backend has no "write nothing" mode: it defaults
``--touch-dir`` to ``"./"`` and touches unconditionally. That default is the one thing only a
CLI-level test can pin, since ``WorkflowExecutor(touch_dir=None)`` deliberately writes nothing.

Like the rest of this suite it names no real plugin: the graph is built from the host's own
collection builtins, and the ``-p`` selection is the designed specimen.
"""

import pytest
import specimen
from coral_app.cli import DEFAULT_TOUCH_DIR, main
from coral_app.nodestatus import RUNNING, STATUS_SUFFIXES, SUCCEEDED
from specimen import SPECIMEN

# Builtin collection nodes only, so the graph itself needs no plugin.
GRAPH = {
    "workflow": {
        "nodes": {
            "0": {"qualified_id": "0", "type": "list_new"},
            "1": {"qualified_id": "1", "type": "int", "value": 7},
            "2": {"qualified_id": "2", "type": "list_append"},
        },
        "edges": {
            "0": {"source": "0", "target": "2", "source_output": 0, "target_input": 0},
            "1": {"source": "1", "target": "2", "source_output": 0, "target_input": 1},
        },
    }
}


@pytest.fixture
def graph_file(write_graph):
    """The graph, written into this test's isolated working directory."""
    return write_graph(GRAPH)


@pytest.fixture
def installed(monkeypatch, specimen_plugins):
    """Make the specimen plugins the installed ones, as the CLI sees them.

    ``specimen_plugins`` patches only ``load``; the CLI also checks every ``-p`` name against
    ``discover()`` before running anything, so here that lookup reports the specimen too. It is
    patched where the CLI reads it, since ``cli`` imports the name.
    """
    monkeypatch.setattr("coral_app.cli.discover", lambda: sorted(specimen.PLUGINS))


class TestRunTouchDir:
    """``coral run`` and the per-node status markers."""

    def test_the_default_is_the_cwd(self):
        """GIVEN the CLI module
        WHEN its touch-dir default is read
        THEN it is ``"./"``, as in the reference backend — the flag being omitted does not mean
        silence."""
        assert DEFAULT_TOUCH_DIR == "./"

    def test_run_without_the_flag_writes_markers_into_the_cwd(
        self, graph_file, tmp_path, monkeypatch, installed
    ):
        """GIVEN ``coral run <graph>`` with no ``--touch-dir``
        WHEN it executes
        THEN the markers land in the current directory, two per node, and the graph file is left
        alone. This is the reference default, and the platform relies on it: it runs the backend
        inside the job directory it then watches."""
        monkeypatch.setattr("sys.argv", ["coral", "-p", SPECIMEN, "run", str(graph_file)])

        main()

        markers = sorted(
            path.name for path in tmp_path.iterdir() if path.name.endswith(STATUS_SUFFIXES)
        )
        assert markers == [
            f"0{RUNNING}",
            f"0{SUCCEEDED}",
            f"1{RUNNING}",
            f"1{SUCCEEDED}",
            f"2{RUNNING}",
            f"2{SUCCEEDED}",
        ]
        assert graph_file.exists()

    def test_the_flag_redirects_the_markers(self, graph_file, tmp_path, monkeypatch, installed):
        """GIVEN ``coral run <graph> --touch-dir <dir>`` naming a directory that does not exist
        WHEN it executes
        THEN the directory is created, the markers go there, and none is left in the cwd."""
        target = tmp_path / "job-1" / "status"
        monkeypatch.setattr(
            "sys.argv",
            ["coral", "-p", SPECIMEN, "run", str(graph_file), "--touch-dir", str(target)],
        )

        main()

        assert len([path for path in target.iterdir() if path.name.endswith(STATUS_SUFFIXES)]) == 6
        assert not [path for path in tmp_path.iterdir() if path.name.endswith(STATUS_SUFFIXES)]


class TestRegisterOutput:
    """``coral register`` and the filename the platform probes for."""

    def test_register_without_the_flag_writes_node_types_into_the_cwd(
        self, tmp_path, monkeypatch, installed
    ):
        """GIVEN ``coral register`` with no ``--output``
        WHEN it runs
        THEN ``node_types.json`` appears in the current directory.

        This is the CLI's default and the platform's contract: it probes for that fixed name, and
        the launcher preserves the caller's cwd precisely so the file lands where it stands. The
        library's own default is a different string, reachable only by calling
        ``save_registry_to_file`` directly."""
        monkeypatch.setattr("sys.argv", ["coral", "-p", SPECIMEN, "register"])

        main()

        assert (tmp_path / "node_types.json").exists()

    def test_the_flag_redirects_the_file(self, tmp_path, monkeypatch, installed):
        """GIVEN ``coral register --output=<name>``
        WHEN it runs
        THEN that name is written and the default one is not."""
        monkeypatch.setattr(
            "sys.argv", ["coral", "-p", SPECIMEN, "register", "--output=custom.json"]
        )

        main()

        assert (tmp_path / "custom.json").exists()
        assert not (tmp_path / "node_types.json").exists()


class TestPlugins:
    """``coral plugins`` — the names ``-p`` accepts."""

    def test_lists_the_installed_names_one_per_line(self, monkeypatch, capsys, installed):
        """GIVEN the specimen plugins installed
        WHEN ``coral plugins`` runs
        THEN it prints their names sorted, one per line, and nothing else."""
        monkeypatch.setattr("sys.argv", ["coral", "plugins"])

        main()

        assert capsys.readouterr().out == "".join(f"{name}\n" for name in sorted(specimen.PLUGINS))

    def test_prints_nothing_when_none_is_installed(self, monkeypatch, capsys):
        """GIVEN no plugin installed
        WHEN ``coral plugins`` runs
        THEN it prints nothing and exits normally."""
        monkeypatch.setattr("coral_app.cli.discover", lambda: [])
        monkeypatch.setattr("sys.argv", ["coral", "plugins"])

        main()

        assert capsys.readouterr().out == ""


class TestPluginSelection:
    """A ``-p`` value naming the wrong plugins is refused before any subcommand runs."""

    def test_unknown_names_are_refused_before_the_touch_dir_is_prepared(
        self, graph_file, tmp_path, monkeypatch, capsys, installed
    ):
        """GIVEN ``coral -p`` naming the specimen plus two plugins that are not installed
        WHEN ``run --touch-dir <dir>`` is invoked
        THEN it exits with status 2, naming both unknown plugins and the installed ones, and the
        touch directory is never created."""
        target = tmp_path / "status"
        monkeypatch.setattr(
            "sys.argv",
            [
                "coral",
                "-p",
                f"{SPECIMEN},nope,other",
                "run",
                str(graph_file),
                "--touch-dir",
                str(target),
            ],
        )

        with pytest.raises(SystemExit) as exit_info:
            main()

        assert exit_info.value.code == 2
        error = capsys.readouterr().err
        assert "unknown plugins 'nope', 'other'" in error
        assert f"installed: {', '.join(sorted(specimen.PLUGINS))}" in error
        assert not target.exists()

    def test_a_name_given_twice_is_refused(self, tmp_path, monkeypatch, capsys, installed):
        """GIVEN ``coral -p`` naming the specimen twice
        WHEN ``register`` is invoked
        THEN it exits with status 2 naming the repeated plugin, and no registry is written."""
        monkeypatch.setattr("sys.argv", ["coral", "-p", f"{SPECIMEN},{SPECIMEN}", "register"])

        with pytest.raises(SystemExit) as exit_info:
            main()

        assert exit_info.value.code == 2
        assert f"plugin {SPECIMEN!r} named more than once" in capsys.readouterr().err
        assert not (tmp_path / "node_types.json").exists()
