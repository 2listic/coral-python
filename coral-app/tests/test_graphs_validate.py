"""Every graph this package ships is **valid**, checked without executing it.

The graph JSON is the other half of the contract with the DealiiX platform, and validating one is
free: constructing a ``Graph`` runs all nine checks — declared nodes, no subgraph, unique
``qualified_id``, known node types, contiguous ``target_input``, arity, ``source_output`` range, edge
type compatibility, acyclicity — and touches no callable. Executing one, by contrast, costs whatever
the graph does.

Separating the two is what lets the format be pinned at ~0 ms per graph. The graphs here happen to be
cheap to run as well — they are the host's collection examples, which ``test_examples.py`` executes —
but for a phiflow export the same guard is the difference between milliseconds and half a minute.

Cases are discovered from disk: a graph added to ``examples/`` is covered the day it lands. Nothing
declares which plugins these need, because the owning directory already answers that — they are
under ``coral-app/``, so they need **none**.
"""

from pathlib import Path

import pytest
from coral_app import PRIMITIVES_MAP, build_class_map, build_function_map
from coral_app.graph import Graph
from coral_app.nodeports import build_port_table
from host_suite import EXAMPLES


def shipped_graphs():
    """Every graph JSON this package ships, one parametrised case each."""
    return [pytest.param(path, id=path.name) for path in sorted(EXAMPLES.rglob("*.json"))]


@pytest.fixture(scope="module")
def port_table():
    """The port table for the host alone: the primitives plus the builtin collection functions."""
    return build_port_table(
        function_map=build_function_map(include=[]),
        class_map=build_class_map(include=[]),
        primitives=PRIMITIVES_MAP,
    )


class TestShippedGraphsAreValid:
    """Construct each graph; never execute one."""

    @pytest.mark.parametrize("path", shipped_graphs())
    def test_graph_constructs(self, path: Path, port_table):
        """GIVEN a graph this package ships
        WHEN a Graph is constructed from it against the host's own node types
        THEN it passes every check, and orders all of its nodes.

        The order assertion is what makes this more than "it parsed": a node missing from the order
        would mean the topological sort never scheduled it."""
        graph = Graph.from_file(str(path), port_table)

        assert sorted(graph.order) == sorted(graph.nodes)

    def test_some_graphs_were_found(self):
        """GIVEN the discovery glob above
        WHEN it runs against this package
        THEN it found graphs — an empty parametrisation would pass as zero silent cases."""
        assert shipped_graphs(), f"no graphs found under {EXAMPLES}"
