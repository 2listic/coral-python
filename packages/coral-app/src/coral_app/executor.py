from contextlib import nullcontext
from typing import Any, List, Optional

from coral_app import PRIMITIVES_MAP, build_class_map, build_function_map, discover
from coral_app.graph import Graph
from coral_app.nodeports import CONSTRUCTOR, FUNCTION, METHOD, PRIMITIVE, build_port_table
from coral_app.nodestatus import NodeStatusDir, qualified_ids


class WorkflowExecutor:
    """Stage 4: walk a validated graph, calling each node in dependency order.

    One job. The graph is read, checked and ordered by :class:`~coral_app.graph.Graph` during
    construction, so by the time ``execute()`` runs there is nothing left to verify: collect a
    node's inputs from the results so far, resolve its callable, call it, store the result.
    """

    def __init__(
        self,
        workflow_file: str,
        plugins: Optional[List[str]] = None,
        touch_dir: Optional[str] = None,
    ):
        """Prepare the status directory, load the plugins, then read and validate the workflow.

        A wiring error raises here, before any node runs — the point of validating up front is that
        a long simulation is never spent on a graph already known to be broken.

        The status directory is prepared *first*, ahead of plugin loading and validation, for three
        reasons: it is what the C++ backend does; a bad path then fails before phiflow is imported;
        and a graph that fails validation leaves the platform an **empty** directory rather than the
        stale timeline of an earlier job.

        ``touch_dir=None`` means "write nothing": this is a library object, and it should do no
        filesystem I/O nobody asked for. The C++-faithful default of the cwd belongs to the CLI,
        which is where the platform's contract actually lives.

        Args:
            workflow_file: Path to the workflow JSON file
            plugins: List of plugin names to load. If None, loads every discovered plugin.
            touch_dir: Directory to write per-node status markers into, or None to write none.

        Raises:
            OSError: if ``touch_dir`` cannot be created or cleaned.
            ValueError: if the graph does not agree with the loaded plugins' node types, or two of
                its nodes declare the same ``qualified_id``.
        """
        self.status = NodeStatusDir(touch_dir) if touch_dir else None

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

        # Built whether or not markers are written: a duplicate `qualified_id` is a defect in the
        # graph, and a graph must not become invalid only once someone passes --touch-dir.
        self.qualified_ids = qualified_ids(self.graph.nodes)
        self._warn_auto_qualified_ids()

        self.results = {}

    def execute(self):
        """Execute the workflow, returning every node's result keyed by node id.

        Each node is bracketed by two lines in the log and, when a status directory was configured,
        by its three markers — written by the collaborator rather than here, so that "``.failed`` is
        written before the exception escapes" is a property of one testable object instead of a
        discipline this walk has to keep. Everything raising inside the block is covered: a plugin
        function, the method-instance check, the output-arity check.
        """
        print(f"Execution order: {self.graph.order}\n")

        for node_id in self.graph.order:
            node = self.graph.node(node_id)
            ports = self.graph.ports_of(node_id)
            kind = ports.kind
            qualified_id = self.qualified_ids[node_id]

            # The pair of lines is printed whatever the flag says, which is how a failing node is
            # named: the exception itself is propagated untouched, so its message must not have to
            # carry the node id (see the plan's "Why not C++'s wrapped exception").
            print(f"Start running node {node_id} [{qualified_id}] (type = {node['type']})")

            status = self.status.node(qualified_id) if self.status else nullcontext()
            with status:
                if kind == PRIMITIVE:
                    self.results[node_id] = self._convert(node)
                    print(f"{node_id} (primitive) = {self.results[node_id]}")
                else:
                    values = self._input_values(node_id)
                    target, arguments = self._resolve(node_id, node["type"], kind, values)

                    # Inputs arrive in port order, which is parameter order, so a positional call
                    # binds them correctly — no need to look at the callable's signature.
                    result = target(*arguments)
                    self._check_output_arity(node_id, node["type"], ports, result)
                    self.results[node_id] = result

                    if kind == CONSTRUCTOR:
                        print(f"{node_id} (constructor {node['type']}) = {self.results[node_id]}")

            print(f"Node {node_id} [{qualified_id}] (type = {node['type']}) run")
            print()

        print("All nodes executed successfully!")
        return self.results

    def _warn_auto_qualified_ids(self) -> None:
        """Report, in one line, the nodes whose status filenames had to be invented.

        The C++ loader warns once per node; no graph this repo ships carries a ``qualified_id``, so
        that would be a wall of text before execution starts. Same information, no noise.
        """
        auto = [
            node_id
            for node_id, node in self.graph.nodes.items()
            if node.get("qualified_id") is None
        ]
        if auto:
            print(
                f"Warning: {len(auto)} of {len(self.graph.nodes)} nodes declare no qualified_id; "
                f"status filenames auto-generated (e.g. node {auto[0]} -> "
                f"{self.qualified_ids[auto[0]]!r})"
            )

    @staticmethod
    def _check_output_arity(node_id: str, node_type: str, ports, result) -> None:
        """A node declaring more than one output must return a tuple of exactly that many.

        The port table's output arity comes from a return annotation, which is a *claim* by the
        function's author. Everything downstream trusts it: the registry emits that many sockets,
        graph checks 5 and 6 bound and type an edge by it, and :meth:`_input_values` indexes with
        it. This is the one place the claim meets what the function actually returned.

        Confronting them here — at the node that made the claim, right after the call — rather than
        at a consumer's edge is deliberate: it fires whether or not the offending port is wired, so
        an under-declared node cannot slip through by nobody reading its last output, and the error
        names the function whose annotation is wrong rather than the graph that believed it.

        Only ``n > 1`` is checkable. At ``n == 1`` a returned tuple is legitimate — that is exactly
        the ``-> tuple`` case issue #31 turns on — so there is nothing to compare. At ``n == 0`` the
        value is unreachable anyway: graph check 5 rejects every outgoing edge of a node with no
        outputs.

        Raises:
            ValueError: if the result is not a tuple, or is a tuple of the wrong length.
        """
        expected = len(ports.outputs)
        if expected <= 1:
            return

        if not isinstance(result, tuple):
            raise ValueError(
                f"Node {node_id} ({node_type}) declares {expected} outputs but returned "
                f"{type(result).__name__}"
            )

        if len(result) != expected:
            raise ValueError(
                f"Node {node_id} ({node_type}) declares {expected} outputs but returned "
                f"a tuple of {len(result)}"
            )

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
        from the results of the node it comes from.

        Whether that result is a *bundle* of outputs to index into is decided by the **port table**,
        never by the value. How many outputs a node has is a static fact, settled in stage 2 from
        the return annotation; a runtime ``isinstance(value, tuple)`` cannot tell "three outputs,
        bundled" from "one output that happens to be a tuple", and answering it that way was
        issue #31. ``graph.py:_output_annotation`` asks the same question the same way.

        So a single-output node passes its value on whole whatever ``source_output`` says — the
        three spellings graph check 5 accepts for "the only output" (``0``, ``-1``, and the key
        omitted) therefore deliver one and the same value. A multi-output node always indexes, and
        the index is in range because check 5 bounded it by the declared output count and
        :meth:`_check_output_arity` confronted that count with what the node actually returned.
        """
        values = []
        for edge in self.graph.inputs_of(node_id):
            if edge.source not in self.results:
                raise ValueError(f"Node {edge.source} hasn't been executed yet!")
            value = self.results[edge.source]

            if len(self.graph.ports_of(edge.source).outputs) > 1:
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
