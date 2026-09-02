"""
Every graph file the repo ships keys its nodes and edges by decimal integer.

The protocol keys nodes by integer, and only the reference backend enforces it. Three platform
mechanisms rest on the same invariant: the editor's exporter
``parseInt``s every edge endpoint, the editor's id counter ``parseInt``s every node id to find the
next free one, and ``qualified_id`` joins ancestor ids with ``_``. ``coral_app.graph`` takes the
opposite position on purpose — it coerces endpoints with ``str()`` and treats ids as opaque — so a
graph with word ids runs here and nowhere else, silently, which is what happened to the collection
examples before this module existed.

The same reasoning covers ``qualified_id``, which every node must declare (the host raises without
it) and which the platform's editor writes as the node id at the top level — ``12_3`` only appears
one level down, inside a subnetwork, which this host rejects outright. A shipped graph missing the
field would otherwise be caught only if some test happened to execute it.

This is a check on the *files*, not on the loader: readable ids stay available to the unit tests that
build graphs in memory (``test_graph.py`` uses ``"a"``, ``"b"``, ``"c"`` throughout), while anything
the repo hands to the platform has to be something the platform can read back.

Files are discovered from disk, so a new fixture or example is covered the day it is added. A JSON
file with no ``workflow.nodes`` is not a graph and is skipped; ``test_some_graphs_were_found`` fails
loud if that skip ever swallows everything, because a discovery that finds nothing would otherwise
pass as green.
"""

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
SEARCH_DIRS = (REPO_ROOT / "examples", REPO_ROOT / "tests" / "fixtures")


def _graph_files():
    """Every JSON file under the searched directories that holds a workflow graph."""
    found = []
    for directory in SEARCH_DIRS:
        for path in sorted(directory.rglob("*.json")):
            document = json.loads(path.read_text())
            if isinstance(document.get("workflow"), dict) and "nodes" in document["workflow"]:
                found.append(path)
    return found


GRAPH_FILES = _graph_files()
GRAPH_CASES = [pytest.param(p, id=str(p.relative_to(REPO_ROOT))) for p in GRAPH_FILES]


def _as_id(value):
    """The id ``value`` denotes, or ``None`` if the protocol cannot read one out of it.

    Accepts an ``int`` (what the editor writes for edge endpoints) and a string of digits (what a
    JSON object key can be). Rejects a sign, whitespace and a leading zero: the reference backend
    and the editor both read ``"01"`` as ``1``, so allowing it would let two distinct keys name one
    node.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, str) and value.isdigit() and (value == "0" or value[0] != "0"):
        return int(value)
    return None


def test_some_graphs_were_found():
    """GIVEN the repo's examples and fixtures
    WHEN graph files are discovered from disk
    THEN at least one was found — otherwise every case below passes by vacuum."""
    assert GRAPH_FILES


@pytest.mark.parametrize("path", GRAPH_CASES)
def test_node_ids_are_integers(path):
    """GIVEN a shipped graph file
    WHEN its node ids are read
    THEN each is a decimal integer, and no two denote the same one."""
    nodes = json.loads(path.read_text())["workflow"]["nodes"]

    bad = [key for key in nodes if _as_id(key) is None]
    assert not bad, f"{path.name}: node ids are not decimal integers: {bad}"

    ids = [_as_id(key) for key in nodes]
    assert len(set(ids)) == len(ids), f"{path.name}: two node ids denote the same integer: {ids}"


@pytest.mark.parametrize("path", GRAPH_CASES)
def test_edge_keys_are_integers(path):
    """GIVEN a shipped graph file
    WHEN its edge keys are read
    THEN each is a decimal integer — the shape the editor writes, and what our error messages
    quote."""
    edges = json.loads(path.read_text())["workflow"]["edges"]
    if not isinstance(edges, dict):
        pytest.skip("edges given as a sequence, which has no keys to check")

    bad = [key for key in edges if _as_id(key) is None]
    assert not bad, f"{path.name}: edge keys are not decimal integers: {bad}"


@pytest.mark.parametrize("path", GRAPH_CASES)
def test_edge_endpoints_are_integers(path):
    """GIVEN a shipped graph file
    WHEN each edge's ``source`` and ``target`` are read
    THEN both are integers naming a declared node — the endpoints the platform's exporter
    ``parseInt``s, and where a word id turns into ``null`` on the way back."""
    workflow = json.loads(path.read_text())["workflow"]
    edges = workflow["edges"]
    declared = {_as_id(key) for key in workflow["nodes"]}

    items = edges.items() if isinstance(edges, dict) else enumerate(edges)
    for edge_id, edge in items:
        for endpoint in ("source", "target"):
            value = edge[endpoint]
            assert _as_id(value) is not None, (
                f"{path.name}: edge {edge_id!r} {endpoint} {value!r} is not a decimal integer"
            )
            assert _as_id(value) in declared, (
                f"{path.name}: edge {edge_id!r} {endpoint} {value!r} names no declared node"
            )


@pytest.mark.parametrize("path", GRAPH_CASES)
def test_every_node_declares_a_usable_qualified_id(path):
    """GIVEN a shipped graph file
    WHEN each node's ``qualified_id`` is read
    THEN every node declares one, and each is a non-empty string that can be a filename.

    The field names the node's execution status markers, so the host rejects a graph without it —
    but only when that graph is executed. This is what stops a fixture from being added without
    one. The forbidden characters are the consumer's: it splits each marker filename on ``.``, and a
    path separator would write outside the directory the platform watches."""
    nodes = json.loads(path.read_text())["workflow"]["nodes"]

    missing = [key for key, node in nodes.items() if "qualified_id" not in node]
    assert not missing, f"{path.name}: nodes declare no qualified_id: {missing}"

    for key, node in nodes.items():
        qualified_id = node["qualified_id"]
        assert isinstance(qualified_id, str) and qualified_id, (
            f"{path.name}: node {key!r} declares qualified_id {qualified_id!r}, "
            f"which is not a non-empty string"
        )
        forbidden = [character for character in (".", "/", "\\") if character in qualified_id]
        assert not forbidden, (
            f"{path.name}: node {key!r} declares qualified_id {qualified_id!r}, "
            f"which contains {forbidden}"
        )

    declared = [node["qualified_id"] for node in nodes.values()]
    assert len(set(declared)) == len(declared), (
        f"{path.name}: two nodes declare the same qualified_id: {sorted(declared)}"
    )


@pytest.mark.parametrize("path", GRAPH_CASES)
def test_every_qualified_id_is_its_node_id(path):
    """GIVEN a shipped graph file
    WHEN each node's ``qualified_id`` is compared with its node id
    THEN the two are equal — the convention the platform's editor writes (``PoissonSolverCreation``,
    ``laplace``, ``qualified_id.json`` in the reference repo's ``test_files`` all do this).

    Kept separate from the check above because it is a *convention*, not a requirement: the host
    accepts any unique, filename-safe string, and a nested graph would legitimately use ``12_3``.
    Every graph the repo ships is flat, so here the two must agree."""
    nodes = json.loads(path.read_text())["workflow"]["nodes"]

    # `.get` rather than `[...]`: a missing field is the previous test's failure to report, and a
    # KeyError here would only bury it.
    wrong = {
        key: node.get("qualified_id")
        for key, node in nodes.items()
        if node.get("qualified_id") != key
    }
    assert not wrong, f"{path.name}: qualified_id differs from the node id: {wrong}"
