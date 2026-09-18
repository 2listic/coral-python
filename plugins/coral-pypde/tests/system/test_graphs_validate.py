"""Every graph this plugin ships is **valid**, checked without executing it.

Constructing a ``Graph`` runs all of the host's checks, calls no wrapper and starts no solver, so
the graph-JSON contract is guarded at ~0 ms per file — which matters here because *running* this
plugin's graph costs about twelve seconds.

Unlike the other plugins there is no ``graphs/`` directory to scan: this package ships no editor
export, so its examples are the whole set. Which plugin these graphs need is not inferred at run
time and is tabulated nowhere — they sit under ``plugins/coral-pypde/``, so they need ``pypde``.
"""

import pytest
from coral_app import PRIMITIVES_MAP, build_class_map, build_function_map
from coral_app.graph import Graph
from coral_app.nodeports import build_port_table
from pypde_suite import EXAMPLES, PLUGIN_NAME


def shipped_graphs():
    """One case per graph JSON this plugin ships."""
    return [pytest.param(path, id=path.name) for path in sorted(EXAMPLES.rglob("*.json"))]


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
        assert shipped_graphs(), f"no graphs found under {EXAMPLES}"


class TestTheWrapperTypesAreEnforced:
    """The payoff of annotating every port with a wrapper type, asserted rather than assumed."""

    def test_a_mismatched_wrapper_is_refused_before_anything_runs(self, port_table):
        """GIVEN a graph wiring a grid into the port that expects a movie
        WHEN a Graph is constructed from it
        THEN it is refused, naming the edge.

        Nothing is executed and py-pde is never called: the refusal comes from the edge-type check
        comparing two annotations. Were these ports ``Any`` — as they are throughout the phiflow
        plugin — the check would skip and this graph would only fail once the solver had run."""
        nodes = {
            "0": {"qualified_id": "0", "type": "int", "value": "8"},
            "1": {"qualified_id": "1", "type": "int", "value": "8"},
            "2": {"qualified_id": "2", "type": "PyPDEUnitGrid"},
            "3": {"qualified_id": "3", "type": "float", "value": "1"},
            "4": {"qualified_id": "4", "type": "PyPDEPlotTracker"},
        }
        edges = {
            "0": {"source": 0, "target": 2, "source_output": 0, "target_input": 0},
            "1": {"source": 1, "target": 2, "source_output": 0, "target_input": 1},
            "2": {"source": 2, "target": 4, "source_output": 0, "target_input": 0},
            "3": {"source": 3, "target": 4, "source_output": 0, "target_input": 1},
        }

        with pytest.raises(ValueError, match="PyPDEUnitGrid"):
            Graph(nodes, edges, port_table)
