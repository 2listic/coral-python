from typing import Any, List, Optional

from coral_app import PRIMITIVES_MAP, build_class_map, build_function_map, discover
from coral_app.graph import Graph
from coral_app.nodeports import CONSTRUCTOR, FUNCTION, METHOD, PRIMITIVE, build_port_table


class WorkflowExecutor:
    """Stage 4: walk a validated graph, calling each node in dependency order.

    One job. The graph is read, checked and ordered by :class:`~coral_app.graph.Graph` during
    construction, so by the time ``execute()`` runs there is nothing left to verify: collect a
    node's inputs from the results so far, resolve its callable, call it, store the result.
    """

    def __init__(self, workflow_file: str, plugins: Optional[List[str]] = None):
        """Load the plugins, then read and validate the workflow.

        A wiring error raises here, before any node runs — the point of validating up front is that
        a long simulation is never spent on a graph already known to be broken.

        Args:
            workflow_file: Path to the workflow JSON file
            plugins: List of plugin names to load. If None, loads every discovered plugin.

        Raises:
            ValueError: if the graph does not agree with the loaded plugins' node types.
        """
        # Build function and class maps based on the specified plugins.
        # None means "every discovered plugin" — the host never names a specific plugin.
        if plugins is None:
            plugins = discover()

        self.function_map = build_function_map(include=plugins)
        self.class_map = build_class_map(include=plugins)
        self.primitives_map = PRIMITIVES_MAP

        print(f"Loaded plugins: {', '.join(plugins)}")
        print(f"Available functions: {len(self.function_map)}")
        print(f"Available classes: {len(self.class_map)}\n")

        self.port_table = build_port_table(self.function_map, self.class_map, self.primitives_map)
        self.graph = Graph.from_file(workflow_file, self.port_table)
        self.results = {}

    def execute(self):
        """Execute the workflow, returning every node's result keyed by node id."""
        print(f"Execution order: {self.graph.order}\n")

        for node_id in self.graph.order:
            node = self.graph.node(node_id)
            kind = self.graph.ports_of(node_id).kind

            if kind == PRIMITIVE:
                self.results[node_id] = self._convert(node)
                print(f"{node_id} (primitive) = {self.results[node_id]}")
                print()
                continue

            values = self._input_values(node_id)
            target, arguments = self._resolve(node_id, node["type"], kind, values)

            # Inputs arrive in port order, which is parameter order, so a positional call binds
            # them correctly — no need to look at the callable's signature.
            self.results[node_id] = target(*arguments)

            if kind == CONSTRUCTOR:
                print(f"{node_id} (constructor {node['type']}) = {self.results[node_id]}")
            print()

        print("All nodes executed successfully!")
        return self.results

    def _convert(self, node: dict):
        """A primitive node's value, cast to the type the node declares.

        The JSON protocol may carry the value as a string, so the declared type does the casting.
        """
        converter = self.primitives_map[node["type"]]

        if converter is type(None):
            return None
        if converter is Any:  # Don't convert value if type is Any
            return node["value"]
        return converter(node["value"])

    def _input_values(self, node_id: str) -> list:
        """The values feeding a node, in port order.

        The graph hands over the incoming edges already sorted by ``target_input``; each is read
        from the results of the node it comes from, unwrapping the requested element of a tuple
        return.
        """
        values = []
        for edge in self.graph.inputs_of(node_id):
            if edge.source not in self.results:
                raise ValueError(f"Node {edge.source} hasn't been executed yet!")
            value = self.results[edge.source]

            if edge.source_output is not None:
                if isinstance(value, tuple) and edge.source_output < len(value):
                    value = value[edge.source_output]

            values.append(value)
        return values

    def _resolve(self, node_id: str, node_type: str, kind: str, values: list):
        """The callable a node runs, and the arguments to pass it.

        This is the one three-way distinction the executor cannot write once: a method's callable is
        produced by one of its own inputs, so it is only known at run time.
        """
        if kind == FUNCTION:
            return self.function_map[node_type], values

        if kind == CONSTRUCTOR:
            return self.class_map[node_type], values

        if kind == METHOD:
            class_name, method_name = node_type.rsplit(".", 1)
            instance = values[0]

            # The only check left in the executor, because it is the only one about a value rather
            # than about wiring: port 0 must really hold an instance of the class.
            if not isinstance(instance, self.class_map[class_name]):
                raise ValueError(
                    f"Method node {node_id} expected instance of {class_name}, "
                    f"got {type(instance).__name__}"
                )

            return getattr(instance, method_name), values[1:]

        raise ValueError(
            f"Unknown node kind: {kind}. Supported kinds: primitive, function, constructor, method"
        )
