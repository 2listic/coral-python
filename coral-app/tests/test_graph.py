"""Tests for graph reading, validation and ordering (stage 3) — ``coral_app.graph``.

Every case is a JSON literal against a hand-written port table, so nothing here needs a plugin
installed: ``Graph`` only ever compares a graph against a table of plain data.

The port table below is the vocabulary the whole file shares:

===================== ================================= ==========================
node type             inputs                            outputs
===================== ================================= ==========================
``int`` ``float``     none                              its own type
``str`` ``any``       none                              its own type
``add``               ``a: float``, ``b: float``        ``float``
``sqrt``              ``x: float``                      ``float``
``label``             ``text: str``                     ``str``
``show``              ``value: float``                  none (returns ``None``)
``split``             ``x: float``                      ``float``, ``str``, ``bool``
``anything``          ``value: Any``                    ``Any``
``Widget``            ``size: float``                   ``Widget``
``Widget.resize``     ``self: Widget``, ``f: float``    ``float``
``Gadget``            ``size: float``                   ``Gadget``
``list_new``          none                              ``list``
``set_new``           none                              ``set``
``dict_new``          none                              ``dict``
``list_size``         ``lst: list``                     ``int``
``set_size``          ``s: set``                        ``int``
``dict_size``         ``d: dict``                       ``int``
===================== ================================= ==========================
"""

from typing import Any

import pytest
from coral_app import PRIMITIVES_MAP
from coral_app.graph import Graph
from coral_app.nodeports import (
    CONSTRUCTOR,
    FUNCTION,
    METHOD,
    PRIMITIVE,
    NodePorts,
    build_port_table,
)


class Widget:
    """A plugin-supplied class."""


class Gadget:
    """An unrelated plugin-supplied class."""


class Sprocket(Widget):
    """A subclass of Widget."""


PORT_TABLE = {
    "int": NodePorts(kind=PRIMITIVE, outputs=[int]),
    "float": NodePorts(kind=PRIMITIVE, outputs=[float]),
    "str": NodePorts(kind=PRIMITIVE, outputs=[str]),
    "bool": NodePorts(kind=PRIMITIVE, outputs=[bool]),
    "any": NodePorts(kind=PRIMITIVE, outputs=[Any]),
    "none": NodePorts(kind=PRIMITIVE, outputs=[type(None)]),
    "add": NodePorts(kind=FUNCTION, inputs=[("a", float), ("b", float)], outputs=[float]),
    "sqrt": NodePorts(kind=FUNCTION, inputs=[("x", float)], outputs=[float]),
    "label": NodePorts(kind=FUNCTION, inputs=[("text", str)], outputs=[str]),
    "show": NodePorts(kind=FUNCTION, inputs=[("value", float)], outputs=[]),
    "split": NodePorts(kind=FUNCTION, inputs=[("x", float)], outputs=[float, str, bool]),
    "anything": NodePorts(kind=FUNCTION, inputs=[("value", Any)], outputs=[Any]),
    "Widget": NodePorts(kind=CONSTRUCTOR, inputs=[("size", float)], outputs=[Widget]),
    "Widget.resize": NodePorts(
        kind=METHOD, inputs=[("self", Widget), ("f", float)], outputs=[float]
    ),
    "Gadget": NodePorts(kind=CONSTRUCTOR, inputs=[("size", float)], outputs=[Gadget]),
    "Sprocket": NodePorts(kind=CONSTRUCTOR, inputs=[("size", float)], outputs=[Sprocket]),
    # Collection-shaped entries, mirroring `coral_app.builtin_nodes`: a creator taking nothing and
    # returning a bare collection, and a consumer taking one. Hand-written like everything else here
    # — the point is the annotations `Graph` compares, not which module they came from.
    "list_new": NodePorts(kind=FUNCTION, inputs=[], outputs=[list]),
    "set_new": NodePorts(kind=FUNCTION, inputs=[], outputs=[set]),
    "dict_new": NodePorts(kind=FUNCTION, inputs=[], outputs=[dict]),
    "list_size": NodePorts(kind=FUNCTION, inputs=[("lst", list)], outputs=[int]),
    "set_size": NodePorts(kind=FUNCTION, inputs=[("s", set)], outputs=[int]),
    "dict_size": NodePorts(kind=FUNCTION, inputs=[("d", dict)], outputs=[int]),
}


def build(nodes, edges, port_table=PORT_TABLE):
    """Build a Graph over the shared port table, supplying each node's ``qualified_id``.

    A node keeps one it declares; otherwise it gets ``str(node_id)`` — which is what the editor
    writes for a flat graph, and what ``tests/invariants/test_graph_corpus.py`` requires of every graph the repo
    ships. Supplying it here keeps the node literals below about wiring and typing; that ``Graph``
    *validates* the field (check 3) is pinned by ``TestQualifiedIds``, which bypasses this helper.
    """
    nodes = {node_id: {"qualified_id": str(node_id), **node} for node_id, node in nodes.items()}
    return Graph(nodes, edges, port_table)


def edge(source, target, target_input=0, **extra):
    """One edge, with ``source_output`` defaulting to port 0."""
    return {
        "source": source,
        "target": target,
        "source_output": 0,
        "target_input": target_input,
        **extra,
    }


class TestOrdering:
    """The execution order, for the shapes a graph can take."""

    def test_simple_dag(self):
        """GIVEN two primitives feeding one function
        WHEN the graph is ordered
        THEN the function comes after both primitives."""
        graph = build(
            {
                "n1": {"type": "float", "value": 1.0},
                "n2": {"type": "float", "value": 2.0},
                "n3": {"type": "add"},
            },
            {"e1": edge("n1", "n3", 0), "e2": edge("n2", "n3", 1)},
        )

        assert graph.order.index("n1") < graph.order.index("n3")
        assert graph.order.index("n2") < graph.order.index("n3")

    def test_parallel_edges_to_one_node(self):
        """GIVEN one primitive wired into both ports of a single node
        WHEN the graph is ordered
        THEN both nodes appear exactly once, the primitive first."""
        graph = build(
            {"n1": {"type": "float", "value": 4.0}, "n2": {"type": "add"}},
            {"e1": edge("n1", "n2", 0), "e2": edge("n1", "n2", 1)},
        )

        assert graph.order == ["n1", "n2"]

    def test_diamond(self):
        """GIVEN a diamond — one source feeding two branches that rejoin at one sink
        WHEN the graph is ordered
        THEN every node appears once, after all of its predecessors."""
        graph = build(
            {
                "src": {"type": "float", "value": 9.0},
                "left": {"type": "sqrt"},
                "right": {"type": "sqrt"},
                "sink": {"type": "add"},
            },
            {
                "e1": edge("src", "left", 0),
                "e2": edge("src", "right", 0),
                "e3": edge("left", "sink", 0),
                "e4": edge("right", "sink", 1),
            },
        )

        assert sorted(graph.order) == ["left", "right", "sink", "src"]
        assert graph.order.index("src") < graph.order.index("left") < graph.order.index("sink")
        assert graph.order.index("src") < graph.order.index("right") < graph.order.index("sink")

    def test_isolated_node(self):
        """GIVEN a graph holding a connected pair plus a node with no edges at all
        WHEN the graph is ordered
        THEN the isolated node is still scheduled, alongside the connected ones."""
        graph = build(
            {
                "n1": {"type": "float", "value": 16.0},
                "n2": {"type": "sqrt"},
                "lonely": {"type": "str", "value": "unconnected"},
            },
            {"e1": edge("n1", "n2", 0)},
        )

        assert sorted(graph.order) == ["lonely", "n1", "n2"]
        assert graph.order.index("n1") < graph.order.index("n2")

    def test_empty_graph(self):
        """GIVEN a graph with no nodes and no edges
        WHEN it is ordered
        THEN the order is empty and no error is raised."""
        assert build({}, {}).order == []

    def test_order_follows_the_graph_not_json_key_order(self):
        """GIVEN independent nodes declared in a jumbled order
        WHEN the graph is ordered
        THEN ready nodes come out sorted, so the order is reproducible."""
        nodes = {
            "c": {"type": "int", "value": 3},
            "a": {"type": "int", "value": 1},
            "b": {"type": "int", "value": 2},
        }

        assert build(nodes, {}).order == ["a", "b", "c"]

    def test_ready_nodes_are_sorted_within_each_batch(self):
        """GIVEN two independent chains whose node ids sort against their dependency order
        WHEN the graph is ordered
        THEN each ready batch is emitted sorted, and predecessors still precede successors."""
        nodes = {
            "d": {"type": "float", "value": 1.0},
            "a": {"type": "sqrt"},
            "b": {"type": "float", "value": 2.0},
            "c": {"type": "sqrt"},
        }
        edges = {"e1": edge("d", "a", 0), "e2": edge("b", "c", 0)}

        assert build(nodes, edges).order == ["b", "d", "a", "c"]


class TestCycles:
    """Cycle detection, and what the error says."""

    def test_cycle_is_rejected_and_named(self):
        """GIVEN two function nodes feeding each other, everything else wired correctly
        WHEN the graph is built
        THEN it raises, keeping the words 'Cycle detected' and naming the cycle path."""
        nodes = {
            "n1": {"type": "add"},
            "n2": {"type": "add"},
            "p1": {"type": "float", "value": 1.0},
            "p2": {"type": "float", "value": 2.0},
        }
        edges = {
            "e1": edge("n1", "n2", 0),
            "e2": edge("n2", "n1", 0),
            "e3": edge("p1", "n1", 1),
            "e4": edge("p2", "n2", 1),
        }

        with pytest.raises(ValueError, match="Cycle detected") as excinfo:
            build(nodes, edges)

        message = str(excinfo.value)
        assert "n1" in message and "n2" in message

    def test_self_loop_is_rejected(self):
        """GIVEN a node wired to itself
        WHEN the graph is built
        THEN the cycle is detected."""
        nodes = {"n1": {"type": "sqrt"}}

        with pytest.raises(ValueError, match="Cycle detected"):
            build(nodes, {"e1": edge("n1", "n1", 0)})


class TestEdgeEndpoints:
    """Check 1: every edge endpoint names a declared node."""

    def test_unknown_target_is_rejected(self):
        """GIVEN an edge pointing at an id the graph does not declare
        WHEN the graph is built
        THEN it raises, naming the edge and the missing id."""
        nodes = {"n1": {"type": "float", "value": 1.0}}

        with pytest.raises(ValueError, match=r"Edge 'e1' names target node 'ghost'"):
            build(nodes, {"e1": edge("n1", "ghost", 0)})

    def test_unknown_source_is_rejected(self):
        """GIVEN an edge coming from an id the graph does not declare
        WHEN the graph is built
        THEN it raises, naming the edge and the missing id."""
        nodes = {"n1": {"type": "sqrt"}}

        with pytest.raises(ValueError, match=r"Edge 'e1' names source node 'ghost'"):
            build(nodes, {"e1": edge("ghost", "n1", 0)})

    def test_a_phantom_node_never_reaches_the_order(self):
        """GIVEN an edge from an undeclared id
        WHEN the graph is built
        THEN it is rejected rather than silently gaining a node — the reason this check runs first."""
        nodes = {"n1": {"type": "sqrt"}}

        with pytest.raises(ValueError, match="does not declare"):
            build(nodes, {"e1": edge("ghost", "n1", 0)})

    def test_numeric_endpoint_ids_are_coerced_to_strings(self):
        """GIVEN edges whose endpoints are JSON numbers rather than strings
        WHEN the graph is built
        THEN they match the string node keys, as the editor's graphs require."""
        nodes = {"1": {"type": "float", "value": 4.0}, "2": {"type": "sqrt"}}
        edges = {"e1": {"source": 1, "target": 2, "source_output": 0, "target_input": 0}}

        assert build(nodes, edges).order == ["1", "2"]

    def test_edge_missing_a_required_key_is_rejected(self):
        """GIVEN an edge with no ``target_input``
        WHEN the graph is built
        THEN it raises rather than failing later with a KeyError."""
        nodes = {"n1": {"type": "float", "value": 1.0}, "n2": {"type": "sqrt"}}
        edges = {"e1": {"source": "n1", "target": "n2", "source_output": 0}}

        with pytest.raises(ValueError, match=r"Edge 'e1' declares no 'target_input'"):
            build(nodes, edges)


class TestNodeTypes:
    """Check 4: every node type has a port-table entry."""

    def test_unknown_node_type_is_rejected(self):
        """GIVEN a node whose type is in no plugin's surface
        WHEN the graph is built
        THEN it raises, naming the node and its type."""
        with pytest.raises(ValueError, match=r"Node 'n1' has unknown type 'nope'"):
            build({"n1": {"type": "nope"}}, {})

    def test_node_without_a_type_is_rejected(self):
        """GIVEN a node declaring no ``type`` at all
        WHEN the graph is built
        THEN it raises, naming the node."""
        with pytest.raises(ValueError, match=r"Node 'n1' declares no 'type'"):
            build({"n1": {"value": 1.0}}, {})

    @pytest.mark.parametrize("collection", ["list", "set", "dict"])
    def test_a_collection_is_not_a_node_type(self, collection):
        """GIVEN a graph naming a collection type as a node
        WHEN the graph is built against the real primitives-only port table
        THEN check 4 rejects it: a collection is built by ``list_new`` and friends, so there is
        exactly one way to make one.

        The table here is built rather than hand-written — the point is what the *host* actually
        offers with no plugin at all, which a literal table could not show.
        """
        port_table = build_port_table(primitives=PRIMITIVES_MAP)

        assert collection not in port_table
        with pytest.raises(ValueError, match=rf"Node 'n1' has unknown type '{collection}'"):
            build({"n1": {"type": collection}}, {}, port_table)


class TestNodeIds:
    """Node ids are read as strings, whatever the caller keyed them by."""

    def test_integer_node_ids_are_coerced_to_strings(self):
        """GIVEN an in-memory graph whose nodes are keyed by ``int``
        WHEN the graph is built and an edge joins them
        THEN both meet as strings: the edge resolves and the order names string ids.

        The editor writes an edge's endpoints as numbers while a JSON object's keys are always
        strings, so ``_read_edges`` coerces its endpoints; coercing there and not here is what used
        to make an int-keyed graph fail as "names no declared node"."""
        graph = build({0: {"type": "float", "value": 1.0}, 1: {"type": "show"}}, {"e1": edge(0, 1)})

        assert graph.order == ["0", "1"]
        assert graph.node("0")["value"] == 1.0
        assert [e.source for e in graph.inputs_of("1")] == ["0"]

    def test_two_ids_denoting_the_same_string_are_rejected(self):
        """GIVEN a graph declaring both ``0`` and ``"0"``
        WHEN it is built
        THEN it raises instead of letting the second declaration overwrite the first.

        Coercion merges the two keys, and silently keeping one of two distinct nodes is exactly the
        kind of incoherence the coercion is there to avoid. A graph from a file cannot reach this:
        JSON object keys are strings already."""
        with pytest.raises(ValueError, match=r"Node id '0' is declared twice"):
            build({0: {"type": "int", "value": 1}, "0": {"type": "int", "value": 2}}, {})


class TestQualifiedIds:
    """Check 3: every node declares a unique, filename-safe ``qualified_id``.

    The rules and their exact messages belong to ``nodestatus.qualified_ids`` and are pinned in
    ``tests/test_nodestatus.py``. What matters here is that **``Graph``** is what applies them, so
    that "a graph that constructs is a graph that can be executed" holds — these cases therefore
    call ``Graph`` directly, bypassing ``build``'s supplied field.
    """

    def test_the_mapping_is_exposed_on_the_graph(self):
        """GIVEN two nodes each declaring a qualified id
        WHEN the graph is built
        THEN it carries the node id -> qualified id mapping the executor names status files by."""
        graph = Graph(
            {
                "n1": {"type": "float", "value": 1.0, "qualified_id": "n1"},
                "n2": {"type": "sqrt", "qualified_id": "4_12"},
            },
            {"e1": edge("n1", "n2", 0)},
            PORT_TABLE,
        )

        assert graph.qualified_ids == {"n1": "n1", "n2": "4_12"}

    def test_a_node_declaring_none_is_rejected(self):
        """GIVEN a node with no qualified_id at all
        WHEN the graph is built
        THEN construction raises — the executor is not where this gets discovered."""
        with pytest.raises(ValueError, match=r"Node 'n1' declares no qualified_id"):
            Graph({"n1": {"type": "float", "value": 1.0}}, {}, PORT_TABLE)

    def test_two_nodes_sharing_one_are_rejected(self):
        """GIVEN two nodes declaring the same qualified_id
        WHEN the graph is built
        THEN construction raises: such a graph orders and wires perfectly well, and would corrupt
        the very timeline its status files exist to show."""
        nodes = {
            "n1": {"type": "float", "value": 1.0, "qualified_id": "same"},
            "n2": {"type": "float", "value": 2.0, "qualified_id": "same"},
        }

        with pytest.raises(ValueError, match=r"Node 'n2' repeats qualified_id 'same'"):
            Graph(nodes, {}, PORT_TABLE)

    def test_one_that_cannot_be_a_filename_is_rejected(self):
        """GIVEN a qualified_id containing a dot
        WHEN the graph is built
        THEN construction raises — the whole rule runs here, not only presence and uniqueness."""
        with pytest.raises(ValueError, match=r"Node 'n1' declares qualified_id 'a\.b'"):
            Graph({"n1": {"type": "float", "value": 1.0, "qualified_id": "a.b"}}, {}, PORT_TABLE)


class TestSubgraphNodes:
    """A node carrying a whole workflow of its own is rejected by name (check 2)."""

    def test_a_node_whose_value_holds_a_workflow_is_rejected(self):
        """GIVEN a subnetwork node, as the platform's editor writes one
        WHEN the graph is built
        THEN it raises saying nested subgraphs are unsupported — not "unknown type".

        This is the one shape in which node ids stop being unique: the inner ``nodes`` object
        numbers from its own zero, and only the ``qualified_id`` (``12_3``) tells the two apart."""
        nested = {
            "type": "coral::Network",
            "value": {"workflow": {"nodes": {"0": {"type": "int", "value": 1}}, "edges": {}}},
        }

        with pytest.raises(ValueError, match=r"Node '12' carries a nested workflow"):
            build({"12": nested}, {})

    def test_a_node_typed_network_is_rejected_even_without_a_value(self):
        """GIVEN a node declaring ``node_type: network`` and nothing nested
        WHEN the graph is built
        THEN it is still rejected — the platform's marker for a subnetwork is enough."""
        with pytest.raises(ValueError, match=r"Node 'n1' carries a nested workflow"):
            build({"n1": {"type": "coral::Network", "node_type": "network"}}, {})

    def test_a_primitive_whose_value_is_a_dict_is_not_a_subgraph(self):
        """GIVEN an ``any`` primitive whose value happens to be a dict
        WHEN the graph is built
        THEN it is accepted: only a ``workflow`` key makes a value a nested graph, so an ordinary
        mapping payload is untouched."""
        graph = build({"n1": {"type": "any", "value": {"nodes": 3}}}, {})

        assert graph.order == ["n1"]


class TestInputPorts:
    """Check 5: for n incoming edges the target_input values are exactly 0..n-1."""

    def test_two_edges_on_one_port_are_rejected(self):
        """GIVEN two edges both landing on input port 0
        WHEN the graph is built
        THEN it raises, naming the node and the ports it received."""
        nodes = {
            "n1": {"type": "float", "value": 1.0},
            "n2": {"type": "float", "value": 2.0},
            "n3": {"type": "add"},
        }
        edges = {"e1": edge("n1", "n3", 0), "e2": edge("n2", "n3", 0)}

        with pytest.raises(ValueError, match=r"Node 'n3' of type 'add' has 2 incoming edges"):
            build(nodes, edges)

    def test_port_index_out_of_range_is_rejected(self):
        """GIVEN a single edge wired to input port 3 of a two-input node
        WHEN the graph is built
        THEN it raises rather than silently dropping the connection."""
        nodes = {"n1": {"type": "float", "value": 1.0}, "n2": {"type": "add"}}

        with pytest.raises(ValueError, match=r"input ports \[3\]"):
            build(nodes, {"e1": edge("n1", "n2", 3)})

    def test_contiguous_ports_are_accepted(self):
        """GIVEN two edges on ports 0 and 1 of a two-input node
        WHEN the graph is built
        THEN it is accepted."""
        nodes = {
            "n1": {"type": "float", "value": 1.0},
            "n2": {"type": "float", "value": 2.0},
            "n3": {"type": "add"},
        }
        edges = {"e1": edge("n1", "n3", 0), "e2": edge("n2", "n3", 1)}

        assert build(nodes, edges).order[-1] == "n3"


class TestArity:
    """Check 6: the incoming edge count equals the type's input count."""

    def test_missing_connection_is_rejected(self):
        """GIVEN a two-input node with only one edge
        WHEN the graph is built
        THEN it raises before execution, naming the counts."""
        nodes = {"n1": {"type": "float", "value": 1.0}, "n2": {"type": "add"}}

        with pytest.raises(
            ValueError, match=r"Node 'n2' of type 'add' expects 2 inputs but received 1"
        ):
            build(nodes, {"e1": edge("n1", "n2", 0)})

    def test_a_defaulted_parameter_still_has_to_be_wired(self):
        """GIVEN a constructor node with nothing connected
        WHEN the graph is built
        THEN it raises — a default in plugin code is not a way to leave a port unwired."""
        with pytest.raises(
            ValueError, match=r"Node 'w' of type 'Widget' expects 1 inputs but received 0"
        ):
            build({"w": {"type": "Widget"}}, {})

    def test_method_instance_port_counts_as_an_input(self):
        """GIVEN a method node wired with an instance and its one parameter
        WHEN the graph is built
        THEN both ports satisfy the arity — the instance is input 0."""
        nodes = {
            "size": {"type": "float", "value": 2.0},
            "w": {"type": "Widget"},
            "f": {"type": "float", "value": 3.0},
            "r": {"type": "Widget.resize"},
        }
        edges = {
            "e1": edge("size", "w", 0),
            "e2": edge("w", "r", 0),
            "e3": edge("f", "r", 1),
        }

        assert build(nodes, edges).order[-1] == "r"

    def test_a_zero_input_node_accepts_no_edges(self):
        """GIVEN ``list_new``, which takes nothing, wired to receive an edge anyway
        WHEN the graph is built
        THEN it raises: 0 input ports against 1 incoming edge.

        The edge uses ``target_input: 0`` deliberately. Any other index would trip check 5 (the
        ``target_input`` values must be exactly ``0..n-1``) first, and the test would pass for the
        wrong reason.
        """
        nodes = {"p": {"type": "float", "value": 1.0}, "n": {"type": "list_new"}}

        with pytest.raises(
            ValueError, match=r"Node 'n' of type 'list_new' expects 0 inputs but received 1"
        ):
            build(nodes, {"e1": edge("p", "n", 0)})

    def test_a_zero_input_node_alone_is_fine(self):
        """GIVEN ``list_new`` with nothing wired into it
        WHEN the graph is built
        THEN it is accepted — unlike a defaulted parameter, it genuinely has no port to wire."""
        assert build({"n": {"type": "list_new"}}, {}).order == ["n"]


class TestOutputPorts:
    """Check 7: source_output names an output the source type actually has."""

    def test_minus_one_is_accepted_on_a_single_output_type(self):
        """GIVEN an edge reading output -1 of a single-output node
        WHEN the graph is built
        THEN it is accepted — both 0 and -1 appear on the wire for one output."""
        nodes = {
            "size": {"type": "float", "value": 2.0},
            "w": {"type": "Widget"},
            "f": {"type": "float", "value": 3.0},
            "r": {"type": "Widget.resize"},
        }
        edges = {
            "e1": edge("size", "w", 0),
            "e2": edge("w", "r", 0, source_output=-1),
            "e3": edge("f", "r", 1),
        }

        assert build(nodes, edges).order[-1] == "r"

    def test_minus_one_is_rejected_on_a_multi_output_type(self):
        """GIVEN an edge reading output -1 of a three-output node
        WHEN the graph is built
        THEN it raises — it would silently yield the last tuple element."""
        nodes = {
            "p": {"type": "float", "value": 1.0},
            "s": {"type": "split"},
            "t": {"type": "sqrt"},
        }
        edges = {"e1": edge("p", "s", 0), "e2": edge("s", "t", 0, source_output=-1)}

        with pytest.raises(ValueError, match=r"Edge 'e2' reads output -1 .* valid: 0 to 2"):
            build(nodes, edges)

    def test_output_index_beyond_the_outputs_is_rejected(self):
        """GIVEN an edge reading output 7 of a single-output node
        WHEN the graph is built
        THEN it raises, naming the edge and what would be valid."""
        nodes = {"p": {"type": "float", "value": 1.0}, "t": {"type": "sqrt"}}
        edges = {"e1": edge("p", "t", 0, source_output=7)}

        with pytest.raises(ValueError, match=r"Edge 'e1' reads output 7 .* valid: 0 or -1"):
            build(nodes, edges)

    def test_reading_from_a_node_that_returns_nothing_is_rejected(self):
        """GIVEN an edge out of a node whose type returns None
        WHEN the graph is built
        THEN it raises — there is nothing to pass on."""
        nodes = {"p": {"type": "float", "value": 1.0}, "s": {"type": "show"}, "t": {"type": "sqrt"}}
        edges = {"e1": edge("p", "s", 0), "e2": edge("s", "t", 0)}

        with pytest.raises(ValueError, match=r"Edge 'e2' .* 'show' returns nothing"):
            build(nodes, edges)

    def test_omitted_source_output_is_accepted_on_a_single_output_type(self):
        """GIVEN an edge with no ``source_output`` key at all
        WHEN the graph is built
        THEN it is accepted, meaning the node's only output."""
        nodes = {"p": {"type": "float", "value": 1.0}, "t": {"type": "sqrt"}}
        edges = {"e1": {"source": "p", "target": "t", "target_input": 0}}

        assert build(nodes, edges).order == ["p", "t"]

    def test_omitted_source_output_is_rejected_on_a_multi_output_type(self):
        """GIVEN an edge with no ``source_output`` out of a three-output node
        WHEN the graph is built
        THEN it raises — which of the three is meant is not knowable."""
        nodes = {
            "p": {"type": "float", "value": 1.0},
            "s": {"type": "split"},
            "t": {"type": "sqrt"},
        }
        edges = {"e1": edge("p", "s", 0), "e2": {"source": "s", "target": "t", "target_input": 0}}

        with pytest.raises(ValueError, match=r"Edge 'e2' reads output None"):
            build(nodes, edges)

    def test_each_output_of_a_tuple_can_be_read(self):
        """GIVEN edges reading outputs 0 and 1 of a three-output node
        WHEN the graph is built
        THEN both are accepted, each against its own element annotation."""
        nodes = {
            "p": {"type": "float", "value": 1.0},
            "s": {"type": "split"},
            "t": {"type": "sqrt"},
            "l": {"type": "label"},
        }
        edges = {
            "e1": edge("p", "s", 0),
            "e2": edge("s", "t", 0, source_output=0),
            "e3": edge("s", "l", 0, source_output=1),
        }

        assert sorted(build(nodes, edges).order) == ["l", "p", "s", "t"]


class TestEdgeTypes:
    """Check 8: the source's output annotation against the target's input annotation."""

    def _wire(self, source_type, target_type):
        """One edge from a primitive/constructor node into port 0 of a target node."""
        nodes = {"a": {"type": source_type, "value": 1}, "b": {"type": target_type}}
        return nodes, {"e1": edge("a", "b", 0)}

    def test_identical_types_are_accepted(self):
        """GIVEN a float primitive feeding a float parameter
        WHEN the graph is built
        THEN it is accepted."""
        assert build(*self._wire("float", "sqrt")).order == ["a", "b"]

    def test_int_into_float_is_accepted(self):
        """GIVEN an int primitive feeding a float parameter
        WHEN the graph is built
        THEN it is accepted — Python's numeric tower widens int to float."""
        assert build(*self._wire("int", "sqrt")).order == ["a", "b"]

    def test_bool_into_float_is_accepted(self):
        """GIVEN a bool primitive feeding a float parameter
        WHEN the graph is built
        THEN it is accepted — bool is an int, and int widens to float."""
        assert build(*self._wire("bool", "sqrt")).order == ["a", "b"]

    def test_str_into_float_is_rejected(self):
        """GIVEN a str primitive feeding a float parameter
        WHEN the graph is built
        THEN it raises, naming both annotations."""
        with pytest.raises(ValueError, match=r"feeds str .* expects float"):
            build(*self._wire("str", "sqrt"))

    def test_float_into_str_is_rejected(self):
        """GIVEN a float primitive feeding a str parameter
        WHEN the graph is built
        THEN it raises — widening does not run backwards into text."""
        with pytest.raises(ValueError, match=r"feeds float .* expects str"):
            build(*self._wire("float", "label"))

    def test_float_into_int_is_rejected(self):
        """GIVEN a float feeding an int parameter
        WHEN the graph is built
        THEN it raises — the tower widens, it does not narrow."""
        table = dict(PORT_TABLE, count=NodePorts(kind=FUNCTION, inputs=[("n", int)], outputs=[int]))
        nodes = {"a": {"type": "float", "value": 1.0}, "b": {"type": "count"}}

        with pytest.raises(ValueError, match=r"feeds float .* expects int"):
            build(nodes, {"e1": edge("a", "b", 0)}, table)

    def test_int_into_bool_is_rejected(self):
        """GIVEN an int primitive feeding a bool parameter
        WHEN the graph is built
        THEN it raises — bool is an int subclass, but widening never lands on bool."""
        table = dict(
            PORT_TABLE, toggle=NodePorts(kind=FUNCTION, inputs=[("flag", bool)], outputs=[bool])
        )
        nodes = {"a": {"type": "int", "value": 5}, "b": {"type": "toggle"}}

        with pytest.raises(ValueError, match=r"feeds int .* expects bool"):
            build(nodes, {"e1": edge("a", "b", 0)}, table)

    def test_bool_into_bool_is_accepted(self):
        """GIVEN a bool primitive feeding a bool parameter
        WHEN the graph is built
        THEN it is accepted — the bool guard must not refuse an exact match."""
        table = dict(
            PORT_TABLE, toggle=NodePorts(kind=FUNCTION, inputs=[("flag", bool)], outputs=[bool])
        )
        nodes = {"a": {"type": "bool", "value": True}, "b": {"type": "toggle"}}

        assert build(nodes, {"e1": edge("a", "b", 0)}, table).order == ["a", "b"]

    def test_any_on_the_source_skips_the_check(self):
        """GIVEN an `any` primitive feeding a float parameter
        WHEN the graph is built
        THEN it is accepted unchecked — the answer is not knowable."""
        assert build(*self._wire("any", "sqrt")).order == ["a", "b"]

    def test_any_on_the_target_skips_the_check(self):
        """GIVEN a str primitive feeding a parameter annotated Any
        WHEN the graph is built
        THEN it is accepted unchecked."""
        assert build(*self._wire("str", "anything")).order == ["a", "b"]

    def test_same_class_is_accepted(self):
        """GIVEN a Widget instance feeding a parameter expecting Widget
        WHEN the graph is built
        THEN it is accepted."""
        nodes = {
            "size": {"type": "float", "value": 2.0},
            "w": {"type": "Widget"},
            "f": {"type": "float", "value": 3.0},
            "r": {"type": "Widget.resize"},
        }
        edges = {"e1": edge("size", "w", 0), "e2": edge("w", "r", 0), "e3": edge("f", "r", 1)}

        assert build(nodes, edges).order[-1] == "r"

    def test_subclass_is_accepted(self):
        """GIVEN a Sprocket (a Widget subclass) feeding a parameter expecting Widget
        WHEN the graph is built
        THEN it is accepted."""
        nodes = {
            "size": {"type": "float", "value": 2.0},
            "s": {"type": "Sprocket"},
            "f": {"type": "float", "value": 3.0},
            "r": {"type": "Widget.resize"},
        }
        edges = {"e1": edge("size", "s", 0), "e2": edge("s", "r", 0), "e3": edge("f", "r", 1)}

        assert build(nodes, edges).order[-1] == "r"

    def test_unrelated_class_is_rejected(self):
        """GIVEN a Gadget feeding a parameter expecting Widget
        WHEN the graph is built
        THEN it raises, naming both classes."""
        nodes = {
            "size": {"type": "float", "value": 2.0},
            "g": {"type": "Gadget"},
            "f": {"type": "float", "value": 3.0},
            "r": {"type": "Widget.resize"},
        }
        edges = {"e1": edge("size", "g", 0), "e2": edge("g", "r", 0), "e3": edge("f", "r", 1)}

        with pytest.raises(ValueError, match=r"feeds Gadget .* expects Widget"):
            build(nodes, edges)

    def test_class_into_a_scalar_is_rejected(self):
        """GIVEN a Widget instance feeding a float parameter
        WHEN the graph is built
        THEN it raises."""
        nodes = {
            "size": {"type": "float", "value": 2.0},
            "w": {"type": "Widget"},
            "t": {"type": "sqrt"},
        }
        edges = {"e1": edge("size", "w", 0), "e2": edge("w", "t", 0)}

        with pytest.raises(ValueError, match=r"feeds Widget .* expects float"):
            build(nodes, edges)

    def test_none_into_a_scalar_is_rejected(self):
        """GIVEN a `none` primitive feeding a float parameter
        WHEN the graph is built
        THEN it raises."""
        with pytest.raises(ValueError, match=r"feeds NoneType .* expects float"):
            build(*self._wire("none", "sqrt"))

    def test_the_annotation_of_the_read_output_is_the_one_checked(self):
        """GIVEN a three-output node whose port 1 is a str
        WHEN that port is wired into a float parameter
        THEN it raises against the element's own annotation, not the tuple's."""
        nodes = {
            "p": {"type": "float", "value": 1.0},
            "s": {"type": "split"},
            "t": {"type": "sqrt"},
        }
        edges = {"e1": edge("p", "s", 0), "e2": edge("s", "t", 0, source_output=1)}

        with pytest.raises(ValueError, match=r"feeds str .* expects float"):
            build(nodes, edges)

    # ── collections ──
    #
    # A bare `list` / `set` / `dict` is a plain class, so check 8 already judges it through
    # `issubclass` with no change to `graph.py`. These cases pin that, because the alternative the
    # project rejected — annotating `List[int]` — would make every one of them *skip* instead.

    @pytest.mark.parametrize(
        "creator,consumer",
        [("list_new", "list_size"), ("set_new", "set_size"), ("dict_new", "dict_size")],
    )
    def test_a_collection_into_its_own_type_is_accepted(self, creator, consumer):
        """GIVEN a collection creator feeding a parameter of that same collection type
        WHEN the graph is built
        THEN it is accepted."""
        assert build(*self._wire(creator, consumer)).order == ["a", "b"]

    @pytest.mark.parametrize(
        "creator,consumer",
        [
            ("list_new", "set_size"),
            ("dict_new", "list_size"),
            ("set_new", "dict_size"),
        ],
    )
    def test_one_collection_into_another_is_rejected(self, creator, consumer):
        """GIVEN a collection feeding a parameter expecting a *different* collection
        WHEN the graph is built
        THEN it raises — the three are unrelated classes, not interchangeable containers."""
        with pytest.raises(ValueError, match=r"feeds \w+ .* expects \w+"):
            build(*self._wire(creator, consumer))

    def test_a_collection_into_a_scalar_is_rejected(self):
        """GIVEN a list feeding a float parameter
        WHEN the graph is built
        THEN it raises: a container is not a number, and the numeric tower does not reach it."""
        with pytest.raises(ValueError, match=r"feeds list .* expects float"):
            build(*self._wire("list_new", "sqrt"))

    def test_a_scalar_into_a_collection_is_rejected(self):
        """GIVEN a str primitive feeding a list parameter
        WHEN the graph is built
        THEN it raises — notably, ``list("abc")`` would have *worked* in Python, which is exactly the
        silent surprise the check exists to prevent."""
        with pytest.raises(ValueError, match=r"feeds str .* expects list"):
            build(*self._wire("str", "list_size"))

    def test_a_collection_into_any_skips_the_check(self):
        """GIVEN a list feeding a parameter annotated Any
        WHEN the graph is built
        THEN it is accepted unchecked — as `list_get`'s Any output feeding a typed port must be."""
        assert build(*self._wire("list_new", "anything")).order == ["a", "b"]

    def test_any_into_a_collection_skips_the_check(self):
        """GIVEN an `any` primitive feeding a list parameter
        WHEN the graph is built
        THEN it is accepted unchecked: `Any` on either side is never judged."""
        assert build(*self._wire("any", "list_size")).order == ["a", "b"]


class TestLookups:
    """What the executor asks a built graph for."""

    def test_inputs_of_returns_edges_sorted_by_target_input(self):
        """GIVEN a node whose edges are declared in reverse port order
        WHEN its inputs are requested
        THEN they come back sorted by ``target_input``, i.e. in parameter order."""
        nodes = {
            "n1": {"type": "float", "value": 1.0},
            "n2": {"type": "float", "value": 2.0},
            "n3": {"type": "add"},
        }
        edges = {"late": edge("n1", "n3", 1), "early": edge("n2", "n3", 0)}

        incoming = build(nodes, edges).inputs_of("n3")

        assert [e.target_input for e in incoming] == [0, 1]
        assert [e.source for e in incoming] == ["n2", "n1"]

    def test_inputs_of_a_source_node_is_empty(self):
        """GIVEN a primitive node
        WHEN its inputs are requested
        THEN the list is empty."""
        assert build({"n1": {"type": "int", "value": 1}}, {}).inputs_of("n1") == []

    def test_node_returns_the_definition(self):
        """GIVEN a primitive node carrying a value
        WHEN the node is requested
        THEN its definition comes back, including the ``qualified_id`` ``build`` supplied for it."""
        graph = build({"n1": {"type": "int", "value": 7}}, {})

        assert graph.node("n1") == {"qualified_id": "n1", "type": "int", "value": 7}

    def test_ports_of_returns_the_table_entry_for_the_node_type(self):
        """GIVEN a function node
        WHEN its ports are requested
        THEN the port-table entry for its type comes back."""
        nodes = {
            "n1": {"type": "float", "value": 1.0},
            "n2": {"type": "float", "value": 2.0},
            "n3": {"type": "add"},
        }
        edges = {"e1": edge("n1", "n3", 0), "e2": edge("n2", "n3", 1)}

        graph = build(nodes, edges)

        assert graph.ports_of("n3") is PORT_TABLE["add"]
        assert graph.ports_of("n1").kind == PRIMITIVE

    def test_edges_accept_a_plain_sequence(self):
        """GIVEN edges as a list rather than the JSON's id -> edge mapping
        WHEN the graph is built
        THEN positions serve as edge names and the graph is ordered normally."""
        nodes = {"n1": {"type": "float", "value": 16.0}, "n2": {"type": "sqrt"}}

        graph = build(nodes, [edge("n1", "n2", 0)])

        assert graph.order == ["n1", "n2"]
        assert graph.edges[0].id == "0"
