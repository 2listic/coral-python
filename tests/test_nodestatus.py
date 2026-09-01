"""Tests for per-node execution status: the filenames, and the markers themselves (issue #30).

Both halves of the platform's convention live in ``coral_app.nodestatus``, and both are tested here
without a graph or an executor in sight — which is the point of the module being a collaborator
rather than a few lines inside ``execute()``: "``.failed`` is written before the exception escapes"
is a property of one object, so it can be asserted directly.

The expected behaviour is the C++ reference backend's, since that is the producer the platform's
consumer was written against.
"""

import shutil

import pytest
from coral_app.nodestatus import (
    FAILED,
    RUNNING,
    STATUS_SUFFIXES,
    SUCCEEDED,
    NodeStatusDir,
    qualified_ids,
)


class TestQualifiedIds:
    """Which name a node's status files are built from — and that every node must supply one."""

    def test_declared_ids_are_used_verbatim(self):
        """GIVEN nodes that each declare a qualified_id
        WHEN the mapping is built
        THEN every id is passed through unchanged — the platform owns that string."""
        nodes = {
            "0": {"type": "int", "qualified_id": "0"},
            "1": {"type": "add", "qualified_id": "1"},
        }

        assert qualified_ids(nodes) == {"0": "0", "1": "1"}

    def test_a_qualified_id_need_not_be_the_node_id(self):
        """GIVEN a node whose qualified_id has nothing to do with its node id
        WHEN the mapping is built
        THEN it is accepted as it stands.

        The two name different things: a node id is unique only within one graph, while the
        qualified id is the node's path through nested subgraphs and is the globally unique one. So
        nothing here derives one from the other."""
        nodes = {"0": {"type": "int", "qualified_id": "4_12"}}

        assert qualified_ids(nodes) == {"0": "4_12"}

    def test_a_missing_id_raises_naming_the_node(self):
        """GIVEN a node that declares no qualified_id
        WHEN the mapping is built
        THEN ValueError names it.

        C++ invents ``<node_id>_auto_<counter>`` here and warns instead. An invented name is not the
        node's identity, so a graph that omits the field would hand the platform a timeline it
        cannot key back to its nodes — better to say so before anything runs."""
        nodes = {"0": {"type": "int", "qualified_id": "0"}, "1": {"type": "add"}}

        with pytest.raises(ValueError, match="'1' declares no qualified_id"):
            qualified_ids(nodes)

    def test_a_numeric_id_raises_naming_the_node(self):
        """GIVEN a node whose qualified_id is a number rather than a string
        WHEN the mapping is built
        THEN ValueError names the node.

        ``12`` and ``"12"`` are distinct dict values that name one file, so a graph declaring both
        would drop a node from the timeline and bump the other's mtime. C++ cannot express it:
        ``get<std::string>()`` throws on a number."""
        nodes = {"0": {"type": "int", "qualified_id": 12}}

        with pytest.raises(ValueError, match="must be a string"):
            qualified_ids(nodes)

    def test_an_empty_id_raises(self):
        """GIVEN a node whose qualified_id is the empty string
        WHEN the mapping is built
        THEN ValueError names the node — the markers would be ``.running``, a dotfile naming no
        node at all."""
        nodes = {"0": {"type": "int", "qualified_id": ""}}

        with pytest.raises(ValueError, match="empty qualified_id"):
            qualified_ids(nodes)

    def test_an_id_containing_a_dot_raises(self):
        """GIVEN a qualified_id with a ``.`` in it
        WHEN the mapping is built
        THEN it is rejected: the consumer splits each marker filename on ``.`` to recover the node,
        so a dot inside the name mis-keys it."""
        nodes = {"0": {"type": "int", "qualified_id": "top.add"}}

        with pytest.raises(ValueError, match=r"contains '\.'"):
            qualified_ids(nodes)

    @pytest.mark.parametrize("separator", ["/", "\\"], ids=["slash", "backslash"])
    def test_an_id_containing_a_path_separator_raises(self, separator):
        """GIVEN a qualified_id spelled as a path
        WHEN the mapping is built
        THEN it is rejected: it would write outside the directory the platform watches, or fail."""
        nodes = {"0": {"type": "int", "qualified_id": f"top{separator}first"}}

        with pytest.raises(ValueError, match="path separator"):
            qualified_ids(nodes)

    def test_a_duplicate_declared_id_raises_naming_it(self):
        """GIVEN two nodes declaring the same qualified_id
        WHEN the mapping is built
        THEN ValueError names the offending id.

        Two nodes writing the same three filenames would corrupt the very timeline these files exist
        to show, and silently — so this raises even when no touch directory is configured."""
        nodes = {
            "0": {"type": "int", "qualified_id": "shared"},
            "1": {"type": "int", "qualified_id": "shared"},
        }

        with pytest.raises(ValueError, match="'shared'"):
            qualified_ids(nodes)

    def test_an_empty_graph_yields_an_empty_mapping(self):
        """GIVEN no nodes
        WHEN the mapping is built
        THEN it is empty and nothing raises."""
        assert qualified_ids({}) == {}


class TestNodeStatusDirSetup:
    """Constructing one prepares the directory — that is all it does, and it is not optional."""

    def test_the_directory_is_created_with_its_parents(self, tmp_path):
        """GIVEN a path whose parents do not exist
        WHEN a NodeStatusDir is constructed over it
        THEN the whole chain is created, so the platform can point us at a fresh job directory."""
        target = tmp_path / "jobs" / "job-1" / "status"

        NodeStatusDir(target)

        assert target.is_dir()

    def test_an_existing_directory_is_accepted(self, tmp_path):
        """GIVEN a directory that already exists
        WHEN a NodeStatusDir is constructed over it
        THEN nothing raises."""
        NodeStatusDir(tmp_path)

        assert tmp_path.is_dir()

    @pytest.mark.parametrize("suffix", STATUS_SUFFIXES)
    def test_stale_markers_are_removed(self, tmp_path, suffix):
        """GIVEN a marker of each kind left behind by an earlier run
        WHEN a NodeStatusDir is constructed over that directory
        THEN it is gone: a stale timeline would otherwise be read as this run's."""
        stale = tmp_path / f"old-node{suffix}"
        stale.touch()

        NodeStatusDir(tmp_path)

        assert not stale.exists()

    def test_nothing_but_markers_is_removed(self, tmp_path):
        """GIVEN a directory holding unrelated files and a subdirectory whose name ends in a marker
              suffix
        WHEN a NodeStatusDir is constructed over it
        THEN only the regular marker files go — with the default of the cwd, this directory is
        routinely someone's project directory."""
        keep = tmp_path / "results.h5"
        keep.touch()
        log = tmp_path / "run.log"
        log.touch()
        directory = tmp_path / "archive.succeeded"
        directory.mkdir()
        marker = tmp_path / "3.running"
        marker.touch()

        NodeStatusDir(tmp_path)

        assert keep.exists()
        assert log.exists()
        assert directory.is_dir()
        assert not marker.exists()

    def test_an_unusable_path_raises_at_construction(self, tmp_path):
        """GIVEN a path that cannot be a directory, because a file sits in the middle of it
        WHEN a NodeStatusDir is constructed over it
        THEN OSError propagates.

        A bad ``--touch-dir`` is a configuration error: failing here costs nothing and happens
        before the plugins are even loaded."""
        blocker = tmp_path / "not-a-dir"
        blocker.write_text("x")

        with pytest.raises(OSError):
            NodeStatusDir(blocker / "status")


class TestNodeStatusDirMarkers:
    """What the context manager writes, and when."""

    def test_running_appears_on_enter_and_succeeded_on_a_clean_exit(self, tmp_path):
        """GIVEN a prepared status directory
        WHEN a node's block is entered and left normally
        THEN ``.running`` exists from the start and ``.succeeded`` joins it at the end — the pair,
        in mtime order, is the timeline the consumer reads."""
        status = NodeStatusDir(tmp_path)

        with status.node("3"):
            assert (tmp_path / f"3{RUNNING}").exists()
            assert not (tmp_path / f"3{SUCCEEDED}").exists()

        assert (tmp_path / f"3{RUNNING}").exists()
        assert (tmp_path / f"3{SUCCEEDED}").exists()
        assert not (tmp_path / f"3{FAILED}").exists()

    def test_markers_are_empty_files(self, tmp_path):
        """GIVEN a node that ran
        WHEN its markers are read
        THEN both are empty: the filename is the whole message, as in C++."""
        status = NodeStatusDir(tmp_path)

        with status.node("3"):
            pass

        assert (tmp_path / f"3{RUNNING}").read_bytes() == b""
        assert (tmp_path / f"3{SUCCEEDED}").read_bytes() == b""

    def test_the_qualified_id_names_the_files(self, tmp_path):
        """GIVEN a node whose qualified id is not its node id
        WHEN its block runs
        THEN the files are named after the qualified id."""
        status = NodeStatusDir(tmp_path)

        with status.node("4_12"):
            pass

        assert {path.name for path in tmp_path.iterdir()} == {
            f"4_12{RUNNING}",
            f"4_12{SUCCEEDED}",
        }

    def test_a_failure_leaves_running_and_failed_and_no_succeeded(self, tmp_path):
        """GIVEN a node whose body raises
        WHEN the exception leaves the block
        THEN ``.failed`` is written and ``.running`` is left in place — that pair is what tells the
        platform which node was in flight when the run died — and no ``.succeeded`` appears."""
        status = NodeStatusDir(tmp_path)

        with pytest.raises(ValueError):
            with status.node("3"):
                raise ValueError("boom")

        assert (tmp_path / f"3{RUNNING}").exists()
        assert (tmp_path / f"3{FAILED}").exists()
        assert not (tmp_path / f"3{SUCCEEDED}").exists()

    def test_the_exception_propagates_unchanged(self, tmp_path):
        """GIVEN a node whose body raises a specific exception
        WHEN it leaves the block
        THEN both its type and its message are exactly what was raised.

        Deliberate, and the one place C++ is not followed: it re-throws a ``runtime_error`` wrapping
        the node id. Here the try/except only exists when a touch directory is configured, so
        wrapping would make the exception's type and message depend on an unrelated flag. The node
        id reaches the log the other way, from the pair of lines ``execute()`` prints."""
        status = NodeStatusDir(tmp_path)
        original = KeyError("missing key")

        with pytest.raises(KeyError) as raised:
            with status.node("3"):
                raise original

        assert raised.value is original

    def test_a_touch_failure_mid_run_warns_once_and_does_not_raise(self, tmp_path, capsys):
        """GIVEN a status directory that disappears after construction
        WHEN two nodes run through it
        THEN neither raises and exactly one warning is printed.

        Once nodes are running, the graph's result is worth more than its telemetry — C++ ignores a
        failed touch entirely (an unchecked ``ofstream``); we warn, but only once, since the same
        failure would otherwise repeat for every marker of every node."""
        status = NodeStatusDir(tmp_path / "status")
        shutil.rmtree(tmp_path / "status")

        with status.node("3"):
            pass
        with status.node("4"):
            pass

        assert capsys.readouterr().out.count("Warning") == 1

    def test_the_body_still_runs_when_the_markers_cannot_be_written(self, tmp_path):
        """GIVEN the same vanished directory
        WHEN a node's block runs
        THEN its body executed — telemetry failing must not skip the node."""
        status = NodeStatusDir(tmp_path / "status")
        shutil.rmtree(tmp_path / "status")
        ran = []

        with status.node("3"):
            ran.append(True)

        assert ran == [True]

    def test_each_node_gets_its_own_files(self, tmp_path):
        """GIVEN several nodes run in sequence
        WHEN the directory is listed
        THEN there are two markers per node, keyed by qualified id."""
        status = NodeStatusDir(tmp_path)

        for qualified_id in ("0", "1"):
            with status.node(qualified_id):
                pass

        assert sorted(path.name for path in tmp_path.iterdir()) == [
            f"0{RUNNING}",
            f"0{SUCCEEDED}",
            f"1{RUNNING}",
            f"1{SUCCEEDED}",
        ]
