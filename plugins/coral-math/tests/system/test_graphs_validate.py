"""Every graph this plugin ships is **valid**, checked without executing it.

The graph JSON is one half of the contract with the DealiiX platform, and three of the files here are
real editor exports — the ground truth for what the editor actually produces. Validating one is free:
constructing a ``Graph`` runs all seven checks and calls nothing. Executing one costs whatever the
graph costs.

Keeping the two apart is what lets the format be pinned cheaply. For this plugin the difference is
small; for phiflow the same guard is milliseconds instead of half a minute, which is why it is written
the same way in every plugin's suite.

Which plugins these graphs need is not inferred at run time and is not tabulated anywhere: they sit
under ``plugins/coral-math/``, so they need ``math``. The owning directory *is* the answer.
"""

import json

import pytest
from coral_app import PRIMITIVES_MAP, build_class_map, build_function_map
from coral_app.graph import Graph
from coral_app.nodeports import build_port_table
from math_suite import GRAPHS, PLUGIN_NAME


def shipped_graphs():
    """One case per graph JSON this plugin ships."""
    return [pytest.param(path, id=path.name) for path in sorted(GRAPHS.rglob("*.json"))]


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
        """GIVEN the discovery glob above
        WHEN it runs against this package
        THEN it found graphs — an empty parametrisation would pass as zero silent cases."""
        assert shipped_graphs(), f"no graphs found under {GRAPHS}"

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
