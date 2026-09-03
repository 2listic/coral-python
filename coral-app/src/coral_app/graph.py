"""Stage 3: read a workflow graph, validate it, and put it in execution order.

Construction is where a graph is judged. Every defect raises ``ValueError`` here — a node that
cannot be identified, a wiring error, an incompatible edge, a cycle — before the first node runs: a
long PhiFlow simulation must never be spent on a graph that was already known to be broken.

The port table (stage 2) arrives as plain data, so this module introspects nothing and knows nothing
about plugins: give it a node/edge dict and a table and it will tell you whether the two agree.
"""

import json
import numbers
from dataclasses import dataclass
from graphlib import CycleError, TopologicalSorter
from typing import Any, Dict, List, Mapping, Optional, Sequence, Union

from coral_app.nodeports import NodePorts
from coral_app.nodestatus import qualified_ids

__all__ = ["Edge", "Graph"]


@dataclass(frozen=True)
class Edge:
    """One connection, as the editor writes it.

    Attributes:
        id: The edge's key in the graph JSON — used to name it in error messages.
        source: Id of the node the value comes from.
        target: Id of the node the value goes to.
        target_input: Which input port of the target this feeds. Parameter order follows it.
        source_output: Which output port of the source this takes, or ``None`` when the JSON omits
            the key. ``-1`` is accepted as a synonym for "the only output".
    """

    id: str
    source: str
    target: str
    target_input: int
    source_output: Optional[int] = None


# Python's numeric tower, widening left to right. `issubclass` cannot express it — `issubclass(int,
# float)` is False, yet an int is accepted wherever a float is expected — so the one relation the
# class hierarchy leaves out is taken from the standard library that defines it. No coral type is
# named here: which types exist is `PRIMITIVES_MAP`'s business, and which type a port has is the
# plugin's.
_NUMERIC_TOWER = (numbers.Integral, numbers.Rational, numbers.Real, numbers.Complex)


def _numeric_rank(annotation: type) -> Optional[int]:
    """The type's position in the numeric tower, or ``None`` if it is not a number."""
    return next(
        (rank for rank, abc in enumerate(_NUMERIC_TOWER) if issubclass(annotation, abc)), None
    )


def _is_compatible(source_annotation, target_annotation) -> bool:
    """Whether a value annotated ``source_annotation`` may feed ``target_annotation``.

    Deliberately narrow — it returns ``True`` whenever the answer is not certain, because wrongly
    refusing a good graph is worse than not checking one:

    - ``Any`` on either side (which is also how a missing annotation arrives): skipped.
    - anything that is not a plain class — a union, a generic alias: skipped, since ``issubclass``
      cannot judge it and the standard library has no subtype test that can.
    - class to class, which covers every primitive and every plugin type: accepted when the source
      is the target or a subclass of it (this is also what makes ``bool`` feed ``int``), or when it
      widens to it numerically. Rejected otherwise.
    - ``bool`` as the *target* is the one exception the tower needs: ``bool`` is an ``int`` subclass,
      so it shares ``int``'s rank, and without a guard any Integral would be accepted where a
      ``bool`` is expected. Widening never lands on ``bool``.
    """
    if source_annotation is Any or target_annotation is Any:
        return True

    if not (isinstance(source_annotation, type) and isinstance(target_annotation, type)):
        return True

    if issubclass(source_annotation, target_annotation):
        return True

    # `bool` is an `int` subclass, so the tower ranks it alongside `int` — without this, any
    # Integral would be accepted where a `bool` is expected. Widening never lands on `bool`.
    if target_annotation is bool:
        return False

    source_rank = _numeric_rank(source_annotation)
    target_rank = _numeric_rank(target_annotation)
    return source_rank is not None and target_rank is not None and source_rank <= target_rank


def _name(annotation) -> str:
    """A short, readable name for an annotation, for error messages."""
    return getattr(annotation, "__name__", None) or str(annotation)


class Graph:
    """A validated, ordered workflow graph.

    Constructing one runs every check; a graph that constructs is a graph that can be executed. The
    executor asks it for the execution order, for a node's incoming edges and for the qualified id
    naming a node's status files, and never touches the edge list itself.

    Attributes:
        qualified_ids: Node id -> qualified id, validated during construction. It lives here rather
            than in the executor because "every node declares a unique, filename-safe
            ``qualified_id``" is a rule about node *identity* — the same family as the id coercion
            in :func:`_read_nodes` — and a graph whose nodes cannot be told apart is not
            executable. The rules themselves stay in :mod:`coral_app.nodestatus`, which owns the
            filename convention they come from.
    """

    def __init__(
        self,
        nodes: Mapping[str, dict],
        edges: Union[Mapping[str, dict], Sequence[dict]],
        port_table: Mapping[str, NodePorts],
    ):
        """Read, validate and order a graph.

        Args:
            nodes: Node id -> node definition (``type``, plus ``value`` for primitives).
            edges: The graph's edges, either as the JSON's id -> edge mapping or as a plain sequence.
            port_table: Node type -> :class:`~coral_app.nodeports.NodePorts`, from
                :func:`~coral_app.nodeports.build_port_table`.

        Raises:
            ValueError: on any structural, identity, wiring, typing or ordering defect — including
                a node that declares no ``qualified_id``, one that cannot be a filename, or one
                another node already declares. The message names the offending node or edge.
        """
        self.nodes: Dict[str, dict] = _read_nodes(nodes)
        self.edges: List[Edge] = _read_edges(edges)
        self.port_table = port_table

        self._check_edges_reference_declared_nodes()
        self._check_no_node_is_a_subgraph()

        # Check 3, and the only one whose rules live in another module: `nodestatus` owns what can
        # be a status filename, this owns when a graph is judged against it. Running it here keeps
        # the promise above true — two nodes sharing a qualified id would otherwise give a graph
        # that constructs and cannot be executed — and it runs whether or not markers are ever
        # written, since a graph must not become valid or invalid depending on --touch-dir.
        self.qualified_ids: Dict[str, str] = qualified_ids(self.nodes)

        self._check_node_types_are_known()

        # Built once, here, so the executor never re-filters the edge list per node.
        self._incoming: Dict[str, List[Edge]] = {node_id: [] for node_id in self.nodes}
        for edge in self.edges:
            self._incoming[edge.target].append(edge)
        for incoming in self._incoming.values():
            incoming.sort(key=lambda edge: edge.target_input)

        self._check_input_ports_are_contiguous()
        self._check_every_input_is_connected()
        self._check_output_ports_exist()
        self._check_edge_types()

        self.order: List[str] = self._build_order()

    @classmethod
    def from_file(cls, workflow_file: str, port_table: Mapping[str, NodePorts]) -> "Graph":
        """Load a graph from a workflow JSON file and validate it.

        Args:
            workflow_file: Path to the workflow JSON; nodes and edges live under ``workflow``.
            port_table: Node type -> :class:`~coral_app.nodeports.NodePorts`.
        """
        with open(workflow_file, "r") as f:
            data = json.load(f)

        workflow = data["workflow"]
        return cls(workflow["nodes"], workflow["edges"], port_table)

    # Lookups the executor uses.

    def node(self, node_id: str) -> dict:
        """The definition of one node."""
        return self.nodes[node_id]

    def ports_of(self, node_id: str) -> NodePorts:
        """The port-table entry describing one node's type."""
        node_type = self.node(node_id)["type"]
        return self.port_table[node_type]

    def inputs_of(self, node_id: str) -> List[Edge]:
        """The node's incoming edges, sorted by ``target_input`` — i.e. in parameter order."""
        return self._incoming[node_id]

    # Validation. Each method is one of the checks, run in the order listed in __init__ — where
    # check 3, the qualified ids, is `nodestatus.qualified_ids` rather than a method here.

    def _check_edges_reference_declared_nodes(self) -> None:
        """Both endpoints of every edge must be declared nodes.

        This runs before anything else because ``TopologicalSorter`` silently materialises an
        unknown predecessor as a node, which would admit a phantom node into the execution order.
        """
        for edge in self.edges:
            for role, node_id in (("source", edge.source), ("target", edge.target)):
                if node_id not in self.nodes:
                    raise ValueError(
                        f"Edge {edge.id!r} names {role} node {node_id!r}, which the graph "
                        f"does not declare"
                    )

    def _check_no_node_is_a_subgraph(self) -> None:
        """No node may carry a nested workflow of its own.

        The platform's editor can put a whole graph inside a node — ``"node_type": "network"``,
        ``"type": "coral::Network"``, with a ``{"workflow": {...}}`` in its ``value``. That is the
        one shape in which **node ids stop being unique**: the inner ``nodes`` object numbers its
        nodes from its own zero, so the same id can name a node at each level, and only the
        ``qualified_id`` (``12_3`` — node 3 inside the subnetwork at node 12) tells them apart.

        This host has no subgraph support, so such a graph is rejected either way — but it would
        otherwise be rejected as "unknown type ``coral::Network``", which sends the reader after a
        missing plugin. Naming the real reason costs three lines and runs before the type check.
        """
        for node_id, node in self.nodes.items():
            value = node.get("value")
            nested = isinstance(value, Mapping) and "workflow" in value
            if nested or node.get("node_type") == "network":
                raise ValueError(
                    f"Node {node_id!r} carries a nested workflow (a subnetwork node); nested "
                    f"subgraphs are not supported. Node ids repeat across nesting levels, so such "
                    f"a graph cannot be read as one flat set of nodes"
                )

    def _check_node_types_are_known(self) -> None:
        """Every node's ``type`` must have a port-table entry."""
        for node_id, node in self.nodes.items():
            if "type" not in node:
                raise ValueError(f"Node {node_id!r} declares no 'type'")
            node_type = node["type"]
            if node_type not in self.port_table:
                raise ValueError(
                    f"Node {node_id!r} has unknown type {node_type!r}: not a loaded primitive, "
                    f"function, class, or method"
                )

    def _check_input_ports_are_contiguous(self) -> None:
        """For n incoming edges, the ``target_input`` values must be exactly 0 to n-1.

        Catches two edges landing on one port, and a port index outside the range the edge count
        allows.
        """
        for node_id, incoming in self._incoming.items():
            ports = [edge.target_input for edge in incoming]
            if sorted(ports) != list(range(len(ports))):
                raise ValueError(
                    f"Node {node_id!r} of type {self.nodes[node_id]['type']!r} has "
                    f"{len(ports)} incoming edges on input ports {sorted(ports)}; "
                    f"expected exactly {list(range(len(ports)))} — a port is duplicated "
                    f"or out of range"
                )

    def _check_every_input_is_connected(self) -> None:
        """Each node must receive exactly as many edges as its type has input ports.

        Every argument must be connected: a parameter's default value in plugin code is *not* a
        way to leave a port unwired.
        """
        for node_id, incoming in self._incoming.items():
            expected = len(self.ports_of(node_id).inputs)
            if len(incoming) != expected:
                node_type = self.nodes[node_id]["type"]
                raise ValueError(
                    f"Node {node_id!r} of type {node_type!r} expects {expected} inputs "
                    f"but received {len(incoming)}"
                )

    def _check_output_ports_exist(self) -> None:
        """Every ``source_output`` must name an output its source type actually has.

        Both ``0`` and ``-1`` appear on the wire for a single-output node, so both are accepted
        there; ``-1`` on a multi-output type is not, since it would silently yield the *last*
        element of the tuple. A type returning ``None`` has nothing to pass on, so any outgoing edge
        from it is an error.
        """
        for edge in self.edges:
            outputs = self.ports_of(edge.source).outputs
            source_type = self.nodes[edge.source]["type"]

            if not outputs:
                raise ValueError(
                    f"Edge {edge.id!r} reads an output of node {edge.source!r}, but its type "
                    f"{source_type!r} returns nothing"
                )

            if len(outputs) == 1:
                valid = edge.source_output in (None, 0, -1)
                allowed = "0 or -1"
            else:
                valid = edge.source_output is not None and 0 <= edge.source_output < len(outputs)
                allowed = f"0 to {len(outputs) - 1}"

            if not valid:
                raise ValueError(
                    f"Edge {edge.id!r} reads output {edge.source_output!r} of node "
                    f"{edge.source!r}, but its type {source_type!r} has {len(outputs)} "
                    f"output(s) — valid: {allowed}"
                )

    def _check_edge_types(self) -> None:
        """Every edge's source annotation must be compatible with its target annotation.

        This is the check that protects a long run: a mismatch fails at t=0 rather than after the
        upstream node has executed. It only sees what the plugins declare — a plugin that annotates
        ``Any`` gets no protection here.
        """
        for edge in self.edges:
            source_annotation = self._output_annotation(edge)
            ports = self.ports_of(edge.target)
            # `target_input` is a safe index here: checks 5 and 6 established that this node's
            # incoming edges occupy exactly ports 0..n-1 for its type's n inputs.
            target_name, target_annotation = ports.inputs[edge.target_input]

            if not _is_compatible(source_annotation, target_annotation):
                raise ValueError(
                    f"Edge {edge.id!r} feeds {_name(source_annotation)} from node "
                    f"{edge.source!r} into parameter {target_name!r} of node {edge.target!r}, "
                    f"which expects {_name(target_annotation)}"
                )

    def _output_annotation(self, edge: Edge):
        """The annotation of the source output an edge reads."""
        outputs = self.ports_of(edge.source).outputs
        if len(outputs) == 1:
            # `None` (key omitted) and -1 both mean "the only output".
            return outputs[0]
        return outputs[edge.source_output]

    def _build_order(self) -> List[str]:
        """Execution order, predecessors first.

        ``TopologicalSorter`` takes ``{node: predecessors}`` — the inverse of an adjacency list.
        Each ready batch is sorted, so the order is a function of the graph rather than of JSON key
        order; that batch is also where concurrent execution of independent branches would hook in.
        """
        predecessors = {node_id: set() for node_id in self.nodes}
        for edge in self.edges:
            predecessors[edge.target].add(edge.source)

        sorter = TopologicalSorter(predecessors)
        try:
            sorter.prepare()
        except CycleError as exc:
            cycle = " -> ".join(str(node_id) for node_id in exc.args[1])
            raise ValueError(f"Cycle detected in workflow: {cycle}") from exc

        order: List[str] = []
        while sorter.is_active():
            batch = sorter.get_ready()
            for node_id in sorted(batch):
                order.append(node_id)
                sorter.done(node_id)
        return order


def _read_nodes(nodes: Mapping[str, dict]) -> Dict[str, dict]:
    """The graph's nodes, keyed by node id as a string.

    Ids are coerced with ``str()`` for the same reason :func:`_read_edges` coerces its endpoints: the
    editor writes an edge's endpoints as numbers while a JSON object's keys are always strings, and
    the two have to meet. Coercing in one place and not the other is how an in-memory graph keyed by
    ``int`` came to be accepted while every edge into it failed as "names no declared node".

    Coercion can merge two keys — ``0`` and ``"0"`` are distinct in a Python dict and name one node
    here — so a collision raises rather than letting the later declaration overwrite the earlier
    one. It cannot happen to a graph loaded from a file: JSON object keys are strings already, and
    the format has no way to spell a duplicate.

    Raises:
        ValueError: if two node ids denote the same string.
    """
    read: Dict[str, dict] = {}
    for node_id, node in nodes.items():
        key = str(node_id)
        if key in read:
            raise ValueError(
                f"Node id {key!r} is declared twice: {node_id!r} and one of the ids before it "
                f"denote the same node"
            )
        read[key] = node
    return read


def _read_edges(edges: Union[Mapping[str, dict], Sequence[dict]]) -> List[Edge]:
    """Turn the JSON's edges into :class:`Edge` objects.

    Accepts the graph JSON's id -> edge mapping (the ids become the edge names used in error
    messages) or a plain sequence, in which case the position is the name. Endpoint ids are coerced
    to ``str``: the editor writes them as numbers in some graphs, while node keys are always strings
    once parsed from JSON.
    """
    items = edges.items() if isinstance(edges, Mapping) else enumerate(edges)

    read = []
    for edge_id, edge in items:
        for required in ("source", "target", "target_input"):
            if required not in edge:
                raise ValueError(f"Edge {str(edge_id)!r} declares no {required!r}")
        read.append(
            Edge(
                id=str(edge_id),
                source=str(edge["source"]),
                target=str(edge["target"]),
                target_input=edge["target_input"],
                source_output=edge.get("source_output"),
            )
        )
    return read
