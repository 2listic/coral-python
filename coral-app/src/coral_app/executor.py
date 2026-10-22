import copy
from contextlib import nullcontext
from typing import List, Optional

from coral_app import PRIMITIVES_MAP, build_class_map, build_function_map, discover
from coral_app.graph import Graph
from coral_app.nodeports import (
    CONSTRUCTOR,
    FUNCTION,
    METHOD,
    PRIMITIVE,
    NodePorts,
    build_port_table,
)
from coral_app.nodestatus import NodeStatusDir


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
        reasons: it is what the reference backend does; a bad path then fails before phiflow is
        imported; and a graph that fails validation leaves the platform an **empty** directory
        rather than the stale timeline of an earlier job.

        ``touch_dir=None`` means "write nothing": this is a library object, and it should do no
        filesystem I/O nobody asked for. The reference default of the cwd belongs to the CLI, which
        is where the platform's contract actually lives.

        Args:
            workflow_file: Path to the workflow JSON file
            plugins: List of plugin names to load. If None, loads every discovered plugin.
            touch_dir: Directory to write per-node status markers into, or None to write none.

        Raises:
            OSError: if ``touch_dir`` cannot be created or cleaned.
            ValueError: from :class:`~coral_app.graph.Graph`, if the graph does not agree with the
                loaded plugins' node types, or one of its nodes declares no ``qualified_id`` or
                repeats another's.
        """
        self.status = NodeStatusDir(touch_dir) if touch_dir else None

        # Build function and class maps based on the specified plugins.
        # None means "every discovered plugin" — the host never names a specific plugin.
        if plugins is None:
            plugins = discover()

        self.function_map = build_function_map(include=plugins)
        self.class_map = build_class_map(include=plugins)
        # (registered class, attribute) -> the function `Plugin.classes` resolved for it: what a
        # method node runs, so no code runs that no plugin declared.
        self._methods = {
            (declaration.target, method.attribute): method.declaration.target
            for declaration in self.class_map.values()
            for method in declaration.methods.values()
        }
        # Registered class -> its key, for the check on every value a node returns.
        self._class_keys = {d.target: key for key, d in self.class_map.items()}
        self._registered = tuple(self._class_keys)

        print(f"Loaded plugins: {', '.join(plugins)}")
        print(f"Available functions: {len(self.function_map)}")
        print(f"Available classes: {len(self.class_map)}\n")

        self.port_table = build_port_table(self.function_map, self.class_map, PRIMITIVES_MAP)
        self.graph = Graph.from_file(workflow_file, self.port_table)

        self.results = {}

    def execute(self):
        """Execute the workflow, returning every node's result keyed by node id.

        Each node is bracketed by two lines in the log and, when a status directory was configured,
        by its three markers — written by the collaborator rather than here, so that "``.failed`` is
        written before the exception escapes" is a property of one testable object instead of a
        discipline this walk has to keep. Everything raising inside the block is covered: a plugin
        function, the method-instance check, the output-arity and output-class checks.
        """
        print(f"Execution order: {self.graph.order}\n")

        for node_id in self.graph.order:
            node = self.graph.node(node_id)
            ports = self.graph.ports_of(node_id)
            kind = ports.kind
            qualified_id = self.graph.qualified_ids[node_id]
            # The reference backend's shape, `node [qid]: name (type)`; an unnamed node drops
            # `: name` rather than printing an empty one or inventing a name nobody wrote.
            name = self.graph.name_of(node_id)
            label = f"{node_id} [{qualified_id}]" + (f": {name}" if name else "")

            # The pair of lines is printed whatever the flag says, which is how a failing node is
            # named: the exception itself is propagated untouched, so its message must not have to
            # carry the node id.
            print(f"Start running node {label} (type = {node['type']})")

            status = self.status.node(qualified_id) if self.status else nullcontext()
            with status:
                if kind == PRIMITIVE:
                    # A copy: a written input is modified in place, and the graph's literal must
                    # stay as it was read.
                    self.results[node_id] = copy.deepcopy(self.graph.literals[node_id])
                    print(f"{node_id} (primitive) = {self.results[node_id]}")
                else:
                    values = self._input_values(node_id)
                    target, arguments = self._resolve(node_id, node["type"], ports, values)

                    # Inputs arrive in port order, which is parameter order, so a positional call
                    # binds them correctly — no need to look at the callable's signature.
                    result = target(*arguments)
                    self._check_output_arity(
                        self.graph.describe(node_id), node["type"], ports, result
                    )
                    outputs = self._outputs(ports, values, result)
                    self._check_output_classes(
                        self.graph.describe(node_id), node["type"], ports, outputs
                    )
                    self.results[node_id] = outputs

                    if kind == CONSTRUCTOR:
                        print(f"{node_id} (constructor {node['type']}) = {self.results[node_id]}")

            print(f"Node {label} (type = {node['type']}) run")
            print()

        print("All nodes executed successfully!")
        return self.results

    @staticmethod
    def _check_output_arity(node: str, node_type: str, ports, result) -> None:
        """A node declaring more than one return value must return a tuple of exactly that many.

        The port table's output arity comes from a return annotation, which is a *claim* by the
        function's author. Everything downstream trusts it: the registry emits that many sockets,
        graph checks 7 and 8 bound and type an edge by it, and :meth:`_input_values` indexes with
        it. This is the one place the claim meets what the function actually returned.

        Confronting them here — at the node that made the claim, right after the call — rather than
        at a consumer's edge is deliberate: it fires whether or not the offending port is wired, so
        an under-declared node cannot slip through by nobody reading its last output, and the error
        names the function whose annotation is wrong rather than the graph that believed it.

        Only the return values are counted (``ports.returns``): a pass-through output is not
        returned, but taken from the input it passes on.

        Only ``n > 1`` is checkable. At ``n == 1`` a returned tuple is legitimate — that is exactly
        the ``-> tuple`` case — so there is nothing to compare. At ``n == 0`` the value is
        unreachable anyway: graph check 7 rejects every outgoing edge of a node with no outputs.

        Raises:
            ValueError: if the result is not a tuple, or is a tuple of the wrong length.
        """
        expected = len(ports.returns)
        if expected <= 1:
            return

        if not isinstance(result, tuple):
            raise ValueError(
                f"Node {node} of type {node_type!r} declares {expected} return values but returned "
                f"{type(result).__name__}"
            )

        if len(result) != expected:
            raise ValueError(
                f"Node {node} of type {node_type!r} declares {expected} return values but returned "
                f"a tuple of {len(result)}"
            )

    def _check_output_classes(self, node: str, node_type: str, ports: NodePorts, outputs) -> None:
        """Every output value of a registered class must be of a registered class itself.

        A method node runs the function declared for its instance's own class, so that class must
        be registered: a function returning an instance of a subclass no plugin registers would
        otherwise hand a method node code nobody declared, with no override check behind it.
        Whatever the port's annotation, ``Any`` included: a value's class is a fact about the value.

        Like the arity check it confronts a declaration with a value, so it cannot run before the
        call; and like it, it runs at the producing node rather than at a consumer, so it fires
        before any consumer of the value has run, and for every value, not only those reaching a
        method.

        Raises:
            ValueError: naming the output and the unregistered class.
        """
        values = outputs if len(ports.outputs) > 1 else (outputs,)
        for index, value in enumerate(values[: len(ports.outputs)]):
            if not isinstance(value, self._registered) or type(value) in self._class_keys:
                continue
            # By `isinstance`, as above, not by the MRO: a virtual subclass of a registered ABC
            # has no registered class in its MRO.
            base = next(c for c in self._registered if isinstance(value, c))
            raise ValueError(
                f"Node {node} of type {node_type!r} produced on output {index} an instance of "
                f"{type(value).__qualname__}, a subclass of {self._class_keys[base]!r} that no "
                f"selected plugin registers; register it, so that the methods it runs are declared"
            )

    @staticmethod
    def _outputs(ports: NodePorts, values: list, result):
        """What a node stores: its outputs in port order, from what it returned and what it passed
        through.

        A pass-through output is the very object its input received, modified in place. The return
        values are what the call returned, a tuple of them when there are several. What is stored is
        a tuple only when the node has more than one output, as :meth:`_input_values` expects, so a
        non-``const`` method returning ``None`` stores its instance itself.
        """
        if len(ports.returns) == len(ports.outputs):
            return result
        if len(ports.returns) > 1:
            returned = iter(result)
        else:
            returned = iter([result] if ports.returns else [])
        outputs = [
            next(returned) if port.passthrough is None else values[port.passthrough]
            for port in ports.outputs
        ]
        return tuple(outputs) if len(outputs) > 1 else outputs[0]

    def _input_values(self, node_id: str) -> list:
        """The values feeding a node, in port order.

        The graph hands over the incoming edges already sorted by ``target_input``; each is read
        from the results of the node it comes from.

        Whether that result is a *bundle* of outputs to index into is decided by the **port table**,
        never by the value. How many outputs a node has is a static fact, settled in stage 2 from
        the return annotation and the written inputs; a runtime ``isinstance(value, tuple)`` cannot
        tell "three outputs, bundled" from "one output that happens to be a tuple", so answering it
        that way is wrong.
        ``graph.py:_output_annotation`` asks the same question the same way.

        So a single-output node passes its value on whole whatever ``source_output`` says — the
        three spellings graph check 7 accepts for "the only output" (``0``, ``-1``, and the key
        omitted) therefore deliver one and the same value. A multi-output node always indexes, and
        the index is in range because check 7 bounded it by the declared output count, and the
        stored bundle has that many: :meth:`_check_output_arity` confronted the return values with
        what the node returned, and :meth:`_outputs` added the pass-throughs.
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

    def _resolve(self, node_id: str, node_type: str, ports: NodePorts, values: list):
        """The callable a node runs, and the arguments to pass it.

        This is the one three-way distinction the executor cannot write once: a method's callable
        depends on one of its own inputs, the instance's class, so it is only known at run time.
        """
        if ports.kind == FUNCTION:
            return self.function_map[node_type].target, values

        if ports.kind == CONSTRUCTOR:
            return self.class_map[node_type].target, values

        if ports.kind == METHOD:
            cls = ports.inputs[0].annotation
            instance = values[0]

            # The only check left in the executor, because it is the only one about a value rather
            # than about wiring: port 0 must really hold an instance of the class. The class is
            # port 0's annotation, the one graph validation checked the edge against.
            if not isinstance(instance, cls):
                raise ValueError(
                    f"Method node {self.graph.describe(node_id)} expected instance of "
                    f"{cls.__name__}, got {type(instance).__name__}"
                )

            # The function resolved for the instance's own class, by attribute rather than node
            # type, since a method may be declared under another name. Never looked up on the
            # instance: only declared code runs, and an override only if its class is registered.
            # That class is registered: a value of a registered class was checked to be of a
            # registered class itself when the node producing it returned.
            return self._methods[(type(instance), ports.attribute)], values

        raise ValueError(
            f"Unknown node kind: {ports.kind}. Supported kinds: primitive, function, constructor, "
            f"method"
        )
