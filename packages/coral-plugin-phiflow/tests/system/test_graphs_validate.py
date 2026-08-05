"""Every graph this plugin ships is **valid**, checked without executing it.

This is the file the whole "validate without executing" idea was written for. Three of these graphs are
real editor exports — including the largest one the platform has produced, 33 nodes and 45 edges — and
until now they were read by *nothing* except tests that ran full fluid simulations to get at them,
between 6 and 33 seconds each. Constructing a ``Graph`` runs all seven checks, calls no wrapper, and
starts no solver.

So the C0 contract is guarded here at ~0 ms per graph, and the simulations are free to be as few and as
explicitly ``slow`` as they like.

Which plugins these graphs need is not inferred at run time and is not tabulated anywhere: they sit
under ``packages/coral-plugin-math/``, so they need ``math``. The owning directory *is* the answer.
"""

import json

import pytest
from coral_app import PRIMITIVES_MAP, build_class_map, build_function_map
from coral_app.graph import Graph
from coral_app.nodeports import build_port_table
from phiflow_suite import EXAMPLES, GRAPHS, PLUGIN_NAME


def shipped_graphs():
    """One case per graph JSON this plugin ships — its exports *and* its examples.

    Both are covered here because validating either costs nothing. That matters most for this plugin:
    running one of these graphs takes 6 to 33 seconds, so "is the format still valid?" would otherwise
    be answerable only by paying for a simulation.
    """
    cases = []
    for directory in (GRAPHS, EXAMPLES):
        for path in sorted(directory.rglob("*.json")):
            cases.append(pytest.param(path, id=f"{directory.name}/{path.name}"))
    return cases


@pytest.fixture(scope="module")
def port_table():
    """The port table for this plugin alone, plus the host's primitives and builtins."""
    return build_port_table(
        function_map=build_function_map(include=[PLUGIN_NAME]),
        class_map=build_class_map(include=[PLUGIN_NAME]),
        primitives=PRIMITIVES_MAP,
    )


class TestShippedGraphsAreValid:
    """Construct each graph; never execute one."""

    @pytest.mark.parametrize("path", shipped_graphs())
    def test_graph_constructs(self, path, port_table):
        """GIVEN a graph this plugin ships
        WHEN a Graph is constructed from it with this plugin selected
        THEN every check passes and all of its nodes are ordered.

        The order assertion is what makes this more than "it parsed": a node missing from the order
        would mean the topological sort never scheduled it."""
        graph = Graph.from_file(str(path), port_table)

        assert sorted(graph.order) == sorted(graph.nodes)

    def test_some_graphs_were_found(self):
        """GIVEN the discovery globs above
        WHEN they run against this package
        THEN they found graphs — an empty parametrisation would pass as zero silent cases."""
        assert shipped_graphs(), f"no graphs found under {GRAPHS} or {EXAMPLES}"

    @pytest.mark.parametrize("path", shipped_graphs())
    def test_this_plugin_is_sufficient(self, path, port_table):
        """GIVEN a graph this plugin ships
        WHEN its node types are looked up
        THEN each is provided by this plugin or by the host itself.

        This is the claim the directory makes by holding the file. If a graph here needed another
        plugin, it would belong to that one — or to nobody, and then to the host."""
        workflow = json.loads(path.read_text())["workflow"]

        for node_id, node in workflow["nodes"].items():
            assert node["type"] in port_table, f"{path.name}:{node_id} needs another plugin"
