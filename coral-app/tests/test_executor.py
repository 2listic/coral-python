"""Stage 4 — ``coral_app.executor``: walking a validated graph and calling each node.

Written entirely against the designed specimen (``specimen.py``), because the executor's behaviour is
not a fact about any plugin: it collects a node's inputs in port order, resolves its callable, binds
positionally, and stores the result. Which callable that is, is the plugin's business.

By the time ``execute()`` runs there is nothing left to verify — ``Graph`` ran all seven checks while
the executor was being constructed. So the failure cases here are about *construction*, and the
success cases are about values.
"""

import pytest
from coral_app.executor import WorkflowExecutor
from specimen import SPECIMEN, Accumulator


def graph(nodes: dict, edges: dict = None) -> dict:
    """Wrap nodes and edges in the workflow envelope the platform exports, supplying each node's
    ``qualified_id``.

    A node keeps one it declares; otherwise it gets ``str(node_id)``. Same convention as
    ``test_graph.py``'s ``build``, and for the same reason: it keeps the node literals below about
    execution rather than about identity.
    """
    nodes = {node_id: {"qualified_id": str(node_id), **node} for node_id, node in nodes.items()}
    return {"workflow": {"nodes": nodes, "edges": edges or {}}}


def edge(source: str, target: str, target_input: int, source_output: int = 0) -> dict:
    """One edge, in the export's shape."""
    return {
        "source": source,
        "target": target,
        "source_output": source_output,
        "target_input": target_input,
    }


@pytest.fixture
def run(write_graph, specimen_plugins):
    """Execute a graph dict against the specimen plugin, returning the results by node id."""

    def _run(nodes: dict, edges: dict = None) -> dict:
        path = write_graph(graph(nodes, edges))
        return WorkflowExecutor(str(path), plugins=[SPECIMEN]).execute()

    return _run


class TestConstruction:
    """What the executor holds once built."""

    def test_it_holds_the_validated_graph_and_the_maps(self, write_graph, specimen_plugins):
        """GIVEN a graph naming a specimen function
        WHEN the executor is constructed
        THEN it exposes the validated graph plus the function and class maps it resolved."""
        path = write_graph(graph({"n": {"type": "make_one"}}))

        executor = WorkflowExecutor(str(path), plugins=[SPECIMEN])

        assert executor.graph.nodes
        assert "add_pair" in executor.function_map
        assert "Accumulator" in executor.class_map

    def test_a_broken_graph_fails_before_any_node_runs(self, write_graph, specimen_plugins):
        """GIVEN a graph wiring a node that does not exist
        WHEN the executor is constructed
        THEN ValueError is raised there — not on a later execute() call.

        This is the whole reason validation moved into construction: a long-running graph must never
        start on wiring already known to be broken."""
        path = write_graph(graph({"n": {"type": "no_such_node"}}))

        with pytest.raises(ValueError):
            WorkflowExecutor(str(path), plugins=[SPECIMEN])


class TestPrimitiveNodes:
    """A primitive casts its ``value`` through the type it declares."""

    @pytest.mark.parametrize(
        "type_name, raw, expected",
        [
            ("int", 42, 42),
            ("int", "42", 42),  # the JSON protocol may carry a number as a string
            ("float", 3.5, 3.5),
            ("float", "3.5", 3.5),
            ("str", "hello", "hello"),
            ("bool", True, True),
        ],
    )
    def test_declared_type_casts_the_value(self, run, type_name, raw, expected):
        """GIVEN a primitive node carrying a value
        WHEN the workflow is executed
        THEN the value is cast by the declared type, whatever the JSON carried."""
        results = run({"n": {"type": type_name, "value": raw}})

        assert results["n"] == expected
        assert isinstance(results["n"], type(expected))

    def test_any_passes_its_value_through_unconverted(self, run):
        """GIVEN a node declared `any`
        WHEN it is executed
        THEN the value arrives exactly as the JSON carried it — no cast is defined for `any`."""
        results = run({"n": {"type": "any", "value": [1, "two"]}})

        assert results["n"] == [1, "two"]

    def test_none_is_none(self, run):
        """GIVEN a node declared `none`
        WHEN it is executed
        THEN its result is None regardless of the value field."""
        results = run({"n": {"type": "none", "value": "ignored"}})

        assert results["n"] is None


class TestFunctionNodes:
    """Function nodes: inputs bound in port order, result stored under the node id."""

    def test_inputs_are_bound_in_port_order(self, run):
        """GIVEN two primitives wired to ports 0 and 1 of a function
        WHEN the workflow is executed
        THEN each value lands on its own parameter."""
        results = run(
            {
                "a": {"type": "float", "value": 5.0},
                "b": {"type": "float", "value": 3.0},
                "f": {"type": "add_pair"},
            },
            {"e0": edge("a", "f", 0), "e1": edge("b", "f", 1)},
        )

        assert results["f"] == 8.0

    def test_target_input_decides_the_order_not_the_edge_order(self, run):
        """GIVEN two edges into an asymmetric function, declared port 1 first
        WHEN the workflow is executed
        THEN the parameters follow `target_input`, not the order the edges appear in the JSON.

        Division makes the swap visible: 8/2 is 4.0 and 2/8 is 0.25."""
        results = run(
            {
                "two": {"type": "float", "value": 2.0},
                "eight": {"type": "float", "value": 8.0},
                "f": {"type": "specimen.ratio"},
            },
            {"e1": edge("two", "f", 1), "e0": edge("eight", "f", 0)},
        )

        assert results["f"] == 4.0

    def test_a_zero_input_function_runs(self, run):
        """GIVEN a function taking no inputs at all
        WHEN it is executed
        THEN it is called and its result stored — no edge is needed to trigger it."""
        results = run({"n": {"type": "make_one"}})

        assert results["n"] == 1.0

    def test_a_none_returning_function_stores_none(self, run):
        """GIVEN a function annotated `-> None`
        WHEN it is executed
        THEN None is stored under its node id, like any other result."""
        results = run(
            {"v": {"type": "float", "value": 1.5}, "r": {"type": "record"}},
            {"e0": edge("v", "r", 0)},
        )

        assert results["r"] is None

    def test_a_dotted_function_name_is_a_function_node(self, run):
        """GIVEN a function registered under a dotted name
        WHEN it is executed
        THEN it is called as a function — the dot does not make it a method lookup."""
        results = run(
            {
                "v": {"type": "float", "value": 12.0},
                "f": {"type": "float", "value": 4.0},
                "s": {"type": "specimen.ratio"},
            },
            {"e0": edge("v", "s", 0), "e1": edge("f", "s", 1)},
        )

        assert results["s"] == 3.0

    def test_chained_functions_feed_each_other(self, run):
        """GIVEN one function's output wired into another's input
        WHEN the workflow is executed
        THEN the downstream node receives the upstream result."""
        results = run(
            {
                "a": {"type": "float", "value": 2.0},
                "b": {"type": "float", "value": 3.0},
                "sum": {"type": "add_pair"},
                "two": {"type": "float", "value": 2.0},
                "half": {"type": "specimen.ratio"},
            },
            {
                "e0": edge("a", "sum", 0),
                "e1": edge("b", "sum", 1),
                "e2": edge("sum", "half", 0),
                "e3": edge("two", "half", 1),
            },
        )

        assert results["sum"] == 5.0
        assert results["half"] == 2.5


class TestMultipleOutputs:
    """``source_output`` selects one element of a tuple result."""

    @pytest.mark.parametrize("port, expected", [(0, 4.0), (1, "4.0"), (2, True)])
    def test_source_output_selects_the_element(self, run, port, expected):
        """GIVEN a function returning three values
        WHEN a downstream edge names one output port
        THEN that element is what the downstream node receives."""
        results = run(
            {
                "v": {"type": "float", "value": 4.0},
                "split": {"type": "split_triple"},
                "sink": {"type": "anything"},
            },
            {"e0": edge("v", "split", 0), "e1": edge("split", "sink", 0, source_output=port)},
        )

        assert results["sink"] == expected

    def test_the_whole_tuple_is_stored_for_the_producing_node(self, run):
        """GIVEN a multi-output function
        WHEN it is executed
        THEN its own result is the whole tuple; the unwrapping happens per consuming edge."""
        results = run(
            {"v": {"type": "float", "value": 4.0}, "split": {"type": "split_triple"}},
            {"e0": edge("v", "split", 0)},
        )

        assert results["split"] == (4.0, "4.0", True)


class TestConstructorNodes:
    """A constructor node instantiates its class."""

    def test_it_stores_an_instance(self, run):
        """GIVEN a constructor wired to one primitive
        WHEN it is executed
        THEN the stored result is an instance holding that value."""
        results = run(
            {"v": {"type": "float", "value": 10.0}, "acc": {"type": "Accumulator"}},
            {"e0": edge("v", "acc", 0)},
        )

        assert isinstance(results["acc"], Accumulator)
        assert results["acc"].start == 10.0

    def test_source_output_minus_one_is_accepted_from_a_constructor(self, run):
        """GIVEN an edge leaving a constructor with `source_output: -1`
        WHEN the workflow is executed
        THEN it is accepted: -1 is the format's "the one unnamed output" for a constructor."""
        results = run(
            {
                "v": {"type": "float", "value": 10.0},
                "acc": {"type": "Accumulator"},
                "t": {"type": "Accumulator.total"},
            },
            {"e0": edge("v", "acc", 0), "e1": edge("acc", "t", 0, source_output=-1)},
        )

        assert results["t"] == 10.0


class TestMethodNodes:
    """A method node's callable comes from its own port 0, so it is only known at run time."""

    def test_the_instance_at_port_zero_is_the_receiver(self, run):
        """GIVEN a constructor feeding port 0 of a method and a value feeding port 1
        WHEN the workflow is executed
        THEN the method runs on that instance with that argument."""
        results = run(
            {
                "start": {"type": "float", "value": 10.0},
                "acc": {"type": "Accumulator"},
                "amount": {"type": "float", "value": 5.0},
                "add": {"type": "Accumulator.add"},
            },
            {
                "e0": edge("start", "acc", 0),
                "e1": edge("acc", "add", 0),
                "e2": edge("amount", "add", 1),
            },
        )

        assert results["add"] == 15.0

    def test_a_method_taking_only_self_runs(self, run):
        """GIVEN a method whose only input is the instance
        WHEN it is executed
        THEN it is called with no further arguments."""
        results = run(
            {
                "start": {"type": "float", "value": 7.0},
                "acc": {"type": "Accumulator"},
                "total": {"type": "Accumulator.total"},
            },
            {"e0": edge("start", "acc", 0), "e1": edge("acc", "total", 0)},
        )

        assert results["total"] == 7.0

    def test_a_subclass_instance_is_accepted(self, run):
        """GIVEN a subclass instance wired into port 0 of a base class's method
        WHEN the workflow is executed
        THEN it runs: the check is `isinstance`, so a subclass is a valid receiver."""
        results = run(
            {
                "start": {"type": "float", "value": 1.0},
                "digits": {"type": "int", "value": 2},
                "acc": {"type": "PreciseAccumulator"},
                "amount": {"type": "float", "value": 2.0},
                "add": {"type": "Accumulator.add"},
            },
            {
                "e0": edge("start", "acc", 0),
                "e1": edge("digits", "acc", 1),
                "e2": edge("acc", "add", 0),
                "e3": edge("amount", "add", 1),
            },
        )

        assert results["add"] == 3.0

    def test_an_unrelated_class_never_reaches_execution(self, write_graph, specimen_plugins):
        """GIVEN an unrelated class's instance wired into port 0 of a method
        WHEN the executor is merely constructed
        THEN it is already refused: both annotations are classes, so graph check 6 can judge the
             edge, and it does — before anything runs."""
        path = write_graph(
            graph(
                {
                    "reading": {"type": "float", "value": 1.0},
                    "gauge": {"type": "Gauge"},
                    "amount": {"type": "float", "value": 2.0},
                    "add": {"type": "Accumulator.add"},
                },
                {
                    "e0": edge("reading", "gauge", 0),
                    "e1": edge("gauge", "add", 0),
                    "e2": edge("amount", "add", 1),
                },
            )
        )

        with pytest.raises(ValueError, match="Accumulator"):
            WorkflowExecutor(str(path), plugins=[SPECIMEN])

    def test_a_value_the_edge_check_cannot_judge_is_rejected_at_run_time(self, run):
        """GIVEN a float reaching a method's port 0 through a function annotated `Any`
        WHEN the workflow is executed
        THEN ValueError names the node, the expected class and what actually arrived.

        This is the one check left inside the executor, and the only reason it must stay there: the
        edge is `Any -> Accumulator`, which check 6 deliberately skips rather than guess, so nothing
        before execution can know the value is not an instance."""
        with pytest.raises(ValueError, match="expected instance of Accumulator"):
            run(
                {
                    "v": {"type": "float", "value": 1.0},
                    "opaque": {"type": "anything"},
                    "amount": {"type": "float", "value": 2.0},
                    "add": {"type": "Accumulator.add"},
                },
                {
                    "e0": edge("v", "opaque", 0),
                    "e1": edge("opaque", "add", 0),
                    "e2": edge("amount", "add", 1),
                },
            )


class TestExecutionOrder:
    """The order comes from the graph; the executor only walks it."""

    def test_a_node_runs_after_its_predecessors(self, run, write_graph, specimen_plugins):
        """GIVEN a diamond — one source feeding two branches that rejoin
        WHEN the order is computed
        THEN every node appears once, after all of its predecessors."""
        path = write_graph(
            graph(
                {
                    "src": {"type": "float", "value": 9.0},
                    "left": {"type": "anything"},
                    "right": {"type": "anything"},
                    "sink": {"type": "add_pair"},
                },
                {
                    "e0": edge("src", "left", 0),
                    "e1": edge("src", "right", 0),
                    "e2": edge("left", "sink", 0),
                    "e3": edge("right", "sink", 1),
                },
            )
        )

        order = WorkflowExecutor(str(path), plugins=[SPECIMEN]).graph.order

        assert sorted(order) == ["left", "right", "sink", "src"]
        assert order.index("src") < order.index("left") < order.index("sink")
        assert order.index("src") < order.index("right") < order.index("sink")

    def test_an_isolated_node_is_still_executed(self, run):
        """GIVEN a node with no edges at all alongside a connected pair
        WHEN the workflow is executed
        THEN the isolated node has a result too."""
        results = run(
            {
                "v": {"type": "float", "value": 2.0},
                "n": {"type": "anything"},
                "lonely": {"type": "str", "value": "unconnected"},
            },
            {"e0": edge("v", "n", 0)},
        )

        assert results["lonely"] == "unconnected"
        assert results["n"] == 2.0

    def test_an_empty_graph_executes_to_nothing(self, run):
        """GIVEN a workflow with no nodes and no edges
        WHEN it is executed
        THEN the results are empty and no error is raised."""
        assert run({}) == {}
