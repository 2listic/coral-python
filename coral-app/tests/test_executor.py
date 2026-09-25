"""Stage 4 — ``coral_app.executor``: walking a validated graph and calling each node.

Written entirely against the designed specimen (``specimen.py``), because the executor's behaviour is
not a fact about any plugin: it collects a node's inputs in port order, resolves its callable, binds
positionally, and stores the result. Which callable that is, is the plugin's business.

By the time ``execute()`` runs there is nothing left to verify — ``Graph`` ran all nine checks while
the executor was being constructed. So the failure cases here are about *construction*, and the
success cases are about values.
"""

import pytest
from coral_app.executor import WorkflowExecutor
from coral_app.nodestatus import FAILED, RUNNING, SUCCEEDED
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
        path = write_graph(graph({"0": {"type": "make_one"}}))

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
        path = write_graph(graph({"0": {"type": "no_such_node"}}))

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
        results = run({"0": {"type": type_name, "value": raw}})

        assert results["0"] == expected
        assert isinstance(results["0"], type(expected))

    def test_any_passes_its_value_through_unconverted(self, run):
        """GIVEN a node declared `any`
        WHEN it is executed
        THEN the value arrives exactly as the JSON carried it — no cast is defined for `any`."""
        results = run({"0": {"type": "any", "value": [1, "two"]}})

        assert results["0"] == [1, "two"]

    def test_none_is_none(self, run):
        """GIVEN a node declared `none`
        WHEN it is executed
        THEN its result is None regardless of the value field."""
        results = run({"0": {"type": "none", "value": "ignored"}})

        assert results["0"] is None


class TestFunctionNodes:
    """Function nodes: inputs bound in port order, result stored under the node id."""

    def test_inputs_are_bound_in_port_order(self, run):
        """GIVEN two primitives wired to ports 0 and 1 of a function
        WHEN the workflow is executed
        THEN each value lands on its own parameter."""
        results = run(
            {
                "0": {"qualified_id": "a", "type": "float", "value": 5.0},
                "1": {"qualified_id": "b", "type": "float", "value": 3.0},
                "2": {"qualified_id": "f", "type": "add_pair"},
            },
            {"0": edge("0", "2", 0), "1": edge("1", "2", 1)},
        )

        assert results["2"] == 8.0

    def test_target_input_decides_the_order_not_the_edge_order(self, run):
        """GIVEN two edges into an asymmetric function, declared port 1 first
        WHEN the workflow is executed
        THEN the parameters follow `target_input`, not the order the edges appear in the JSON.

        Division makes the swap visible: 8/2 is 4.0 and 2/8 is 0.25."""
        results = run(
            {
                "0": {"qualified_id": "two", "type": "float", "value": 2.0},
                "1": {"qualified_id": "eight", "type": "float", "value": 8.0},
                "2": {"qualified_id": "f", "type": "specimen.ratio"},
            },
            {"1": edge("0", "2", 1), "0": edge("1", "2", 0)},
        )

        assert results["2"] == 4.0

    def test_a_zero_input_function_runs(self, run):
        """GIVEN a function taking no inputs at all
        WHEN it is executed
        THEN it is called and its result stored — no edge is needed to trigger it."""
        results = run({"0": {"type": "make_one"}})

        assert results["0"] == 1.0

    def test_a_none_returning_function_stores_none(self, run):
        """GIVEN a function annotated `-> None`
        WHEN it is executed
        THEN None is stored under its node id, like any other result."""
        results = run(
            {
                "0": {"qualified_id": "v", "type": "float", "value": 1.5},
                "1": {"qualified_id": "r", "type": "record"},
            },
            {"0": edge("0", "1", 0)},
        )

        assert results["1"] is None

    def test_a_dotted_function_name_is_a_function_node(self, run):
        """GIVEN a function registered under a dotted name
        WHEN it is executed
        THEN it is called as a function — the dot does not make it a method lookup."""
        results = run(
            {
                "0": {"qualified_id": "v", "type": "float", "value": 12.0},
                "1": {"qualified_id": "f", "type": "float", "value": 4.0},
                "2": {"qualified_id": "s", "type": "specimen.ratio"},
            },
            {"0": edge("0", "2", 0), "1": edge("1", "2", 1)},
        )

        assert results["2"] == 3.0

    def test_chained_functions_feed_each_other(self, run):
        """GIVEN one function's output wired into another's input
        WHEN the workflow is executed
        THEN the downstream node receives the upstream result."""
        results = run(
            {
                "0": {"qualified_id": "a", "type": "float", "value": 2.0},
                "1": {"qualified_id": "b", "type": "float", "value": 3.0},
                "2": {"qualified_id": "sum", "type": "add_pair"},
                "3": {"qualified_id": "two", "type": "float", "value": 2.0},
                "4": {"qualified_id": "half", "type": "specimen.ratio"},
            },
            {
                "0": edge("0", "2", 0),
                "1": edge("1", "2", 1),
                "2": edge("2", "4", 0),
                "3": edge("3", "4", 1),
            },
        )

        assert results["2"] == 5.0
        assert results["4"] == 2.5


class TestMultipleOutputs:
    """``source_output`` selects one element of a tuple result."""

    @pytest.mark.parametrize("port, expected", [(0, 4.0), (1, "4.0"), (2, True)])
    def test_source_output_selects_the_element(self, run, port, expected):
        """GIVEN a function returning three values
        WHEN a downstream edge names one output port
        THEN that element is what the downstream node receives."""
        results = run(
            {
                "0": {"qualified_id": "v", "type": "float", "value": 4.0},
                "1": {"qualified_id": "split", "type": "split_triple"},
                "2": {"qualified_id": "sink", "type": "anything"},
            },
            {"0": edge("0", "1", 0), "1": edge("1", "2", 0, source_output=port)},
        )

        assert results["2"] == expected

    def test_the_whole_tuple_is_stored_for_the_producing_node(self, run):
        """GIVEN a multi-output function
        WHEN it is executed
        THEN its own result is the whole tuple; the unwrapping happens per consuming edge."""
        results = run(
            {
                "0": {"qualified_id": "v", "type": "float", "value": 4.0},
                "1": {"qualified_id": "split", "type": "split_triple"},
            },
            {"0": edge("0", "1", 0)},
        )

        assert results["1"] == (4.0, "4.0", True)


class TestOutputPortResolution:
    """Whether an edge indexes into a result is decided by the port table, never by the value."""

    @pytest.mark.parametrize(
        "extras", [{}, {"source_output": 0}, {"source_output": -1}], ids=["omitted", "0", "-1"]
    )
    def test_the_three_spellings_of_the_only_output_agree(self, run, extras):
        """GIVEN a single-output node whose value happens to be a tuple, read by an edge spelling
             "the only output" as an omitted key, as 0, and as -1
        WHEN the workflow is executed
        THEN all three deliver the whole tuple.

        Graph check 7 calls the three synonyms; this is where that holds in fact. A runtime
        isinstance(result, tuple) cannot tell "two outputs, bundled" from "one output that happens
        to be a tuple" — deciding it that way delivered (10, 20), 10 and 20 to the three."""
        results = run(
            {
                "0": {"qualified_id": "pair", "type": "pair"},
                "1": {"qualified_id": "sink", "type": "anything"},
            },
            {"0": {"source": "0", "target": "1", "target_input": 0, **extras}},
        )

        assert results["1"] == (10, 20)


class TestOutputArity:
    """A node's declared output count, confronted with what it actually returned.

    The arity in the port table comes from a return annotation — a claim by the function's author,
    which the registry, the edge checks and the bundling rule all trust. This is the one place that
    claim meets the value.
    """

    def test_a_short_tuple_raises_naming_the_node_and_both_counts(self, run):
        """GIVEN a function declaring three outputs that returns a tuple of two
        WHEN the graph is executed
        THEN ValueError names the node, its type, and what it returned."""
        with pytest.raises(ValueError) as error:
            run({"0": {"qualified_id": "short", "type": "short_triple"}})

        assert "Node 0 (short_triple) declares 3 outputs but returned a tuple of 2" in str(
            error.value
        )

    def test_it_fires_at_the_producer_not_at_a_consumer(self, run):
        """GIVEN the same over-declaring node, this time with port 0 wired to a sink
        WHEN the graph is executed
        THEN it still raises at the producing node.

        The check runs right after the node returns rather than on a consuming edge, so a node
        whose last output nobody reads cannot slip through."""
        with pytest.raises(ValueError) as error:
            run(
                {
                    "0": {"qualified_id": "short", "type": "short_triple"},
                    "1": {"qualified_id": "sink", "type": "anything"},
                },
                {"0": edge("0", "1", 0)},
            )

        assert "Node 0 (short_triple)" in str(error.value)

    def test_a_non_tuple_result_raises_naming_its_type(self, run):
        """GIVEN a function declaring two outputs that returns a plain int
        WHEN the graph is executed
        THEN ValueError names the type that came back instead of a tuple."""
        with pytest.raises(ValueError) as error:
            run({"0": {"qualified_id": "scalar", "type": "not_a_tuple"}})

        assert "Node 0 (not_a_tuple) declares 2 outputs but returned int" in str(error.value)


class TestConstructorNodes:
    """A constructor node instantiates its class."""

    def test_it_stores_an_instance(self, run):
        """GIVEN a constructor wired to one primitive
        WHEN it is executed
        THEN the stored result is an instance holding that value."""
        results = run(
            {
                "0": {"qualified_id": "v", "type": "float", "value": 10.0},
                "1": {"qualified_id": "acc", "type": "Accumulator"},
            },
            {"0": edge("0", "1", 0)},
        )

        assert isinstance(results["1"], Accumulator)
        assert results["1"].start == 10.0

    def test_source_output_minus_one_is_accepted_from_a_constructor(self, run):
        """GIVEN an edge leaving a constructor with `source_output: -1`
        WHEN the workflow is executed
        THEN it is accepted: -1 is the format's "the one unnamed output" for a constructor."""
        results = run(
            {
                "0": {"qualified_id": "v", "type": "float", "value": 10.0},
                "1": {"qualified_id": "acc", "type": "Accumulator"},
                "2": {"qualified_id": "t", "type": "Accumulator.total"},
            },
            {"0": edge("0", "1", 0), "1": edge("1", "2", 0, source_output=-1)},
        )

        assert results["2"] == 10.0


class TestMethodNodes:
    """A method node's callable comes from its own port 0, so it is only known at run time."""

    def test_the_instance_at_port_zero_is_the_receiver(self, run):
        """GIVEN a constructor feeding port 0 of a method and a value feeding port 1
        WHEN the workflow is executed
        THEN the method runs on that instance with that argument."""
        results = run(
            {
                "0": {"qualified_id": "start", "type": "float", "value": 10.0},
                "1": {"qualified_id": "acc", "type": "Accumulator"},
                "2": {"qualified_id": "amount", "type": "float", "value": 5.0},
                "3": {"qualified_id": "add", "type": "Accumulator.add"},
            },
            {
                "0": edge("0", "1", 0),
                "1": edge("1", "3", 0),
                "2": edge("2", "3", 1),
            },
        )

        assert results["3"] == 15.0

    def test_a_method_taking_only_self_runs(self, run):
        """GIVEN a method whose only input is the instance
        WHEN it is executed
        THEN it is called with no further arguments."""
        results = run(
            {
                "0": {"qualified_id": "start", "type": "float", "value": 7.0},
                "1": {"qualified_id": "acc", "type": "Accumulator"},
                "2": {"qualified_id": "total", "type": "Accumulator.total"},
            },
            {"0": edge("0", "1", 0), "1": edge("1", "2", 0)},
        )

        assert results["2"] == 7.0

    def test_a_subclass_instance_is_accepted(self, run):
        """GIVEN a subclass instance wired into port 0 of a base class's method
        WHEN the workflow is executed
        THEN it runs: the check is `isinstance`, so a subclass is a valid receiver."""
        results = run(
            {
                "0": {"qualified_id": "start", "type": "float", "value": 1.0},
                "1": {"qualified_id": "digits", "type": "int", "value": 2},
                "2": {"qualified_id": "acc", "type": "PreciseAccumulator"},
                "3": {"qualified_id": "amount", "type": "float", "value": 2.0},
                "4": {"qualified_id": "add", "type": "Accumulator.add"},
            },
            {
                "0": edge("0", "2", 0),
                "1": edge("1", "2", 1),
                "2": edge("2", "4", 0),
                "3": edge("3", "4", 1),
            },
        )

        assert results["4"] == 3.0

    def test_an_unrelated_class_never_reaches_execution(self, write_graph, specimen_plugins):
        """GIVEN an unrelated class's instance wired into port 0 of a method
        WHEN the executor is merely constructed
        THEN it is already refused: both annotations are classes, so graph check 6 can judge the
             edge, and it does — before anything runs."""
        path = write_graph(
            graph(
                {
                    "0": {"qualified_id": "reading", "type": "float", "value": 1.0},
                    "1": {"qualified_id": "gauge", "type": "Gauge"},
                    "2": {"qualified_id": "amount", "type": "float", "value": 2.0},
                    "3": {"qualified_id": "add", "type": "Accumulator.add"},
                },
                {
                    "0": edge("0", "1", 0),
                    "1": edge("1", "3", 0),
                    "2": edge("2", "3", 1),
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
                    "0": {"qualified_id": "v", "type": "float", "value": 1.0},
                    "1": {"qualified_id": "opaque", "type": "anything"},
                    "2": {"qualified_id": "amount", "type": "float", "value": 2.0},
                    "3": {"qualified_id": "add", "type": "Accumulator.add"},
                },
                {
                    "0": edge("0", "1", 0),
                    "1": edge("1", "3", 0),
                    "2": edge("2", "3", 1),
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
                    "0": {"qualified_id": "src", "type": "float", "value": 9.0},
                    "1": {"qualified_id": "left", "type": "anything"},
                    "2": {"qualified_id": "right", "type": "anything"},
                    "3": {"qualified_id": "sink", "type": "add_pair"},
                },
                {
                    "0": edge("0", "1", 0),
                    "1": edge("0", "2", 0),
                    "2": edge("1", "3", 0),
                    "3": edge("2", "3", 1),
                },
            )
        )

        executor = WorkflowExecutor(str(path), plugins=[SPECIMEN])
        # The order is node ids; each node's qualified_id gives it back the name it plays here.
        order = [executor.graph.qualified_ids[node_id] for node_id in executor.graph.order]

        assert sorted(order) == ["left", "right", "sink", "src"]
        assert order.index("src") < order.index("left") < order.index("sink")
        assert order.index("src") < order.index("right") < order.index("sink")

    def test_an_isolated_node_is_still_executed(self, run):
        """GIVEN a node with no edges at all alongside a connected pair
        WHEN the workflow is executed
        THEN the isolated node has a result too."""
        results = run(
            {
                "0": {"qualified_id": "v", "type": "float", "value": 2.0},
                "1": {"qualified_id": "n", "type": "anything"},
                "2": {"qualified_id": "lonely", "type": "str", "value": "unconnected"},
            },
            {"0": edge("0", "1", 0)},
        )

        assert results["2"] == "unconnected"
        assert results["1"] == 2.0

    def test_an_empty_graph_executes_to_nothing(self, run):
        """GIVEN a workflow with no nodes and no edges
        WHEN it is executed
        THEN the results are empty and no error is raised."""
        assert run({}) == {}


class TestStatusMarkers:
    """The executor's wiring to ``nodestatus``: the markers a real run leaves on disk.

    The marker mechanics are ``nodestatus``'s own and are tested there, against that object
    directly. What only an executor can show is that a run reaches them at all, that every node
    gets them, and that the directory is prepared before the graph is even read.
    """

    def _executor(self, write_graph, nodes, edges, touch_dir):
        """A WorkflowExecutor over an inline graph, pointed at a status directory."""
        path = write_graph(graph(nodes, edges))
        return WorkflowExecutor(str(path), plugins=[SPECIMEN], touch_dir=str(touch_dir))

    def test_every_node_including_a_primitive_is_marked_succeeded(
        self, write_graph, specimen_plugins, tmp_path
    ):
        """GIVEN a graph of two primitives and a function, run with a touch directory
        WHEN it completes
        THEN each node left a .running and a .succeeded named by its qualified_id, and no .failed.

        Primitives are marked too: the reference backend makes every node a task with no exemption,
        and a graph whose primitives never appear would read as "half the nodes never started"."""
        status = tmp_path / "status"
        executor = self._executor(
            write_graph,
            {
                "0": {"qualified_id": "a", "type": "float", "value": 6.0},
                "1": {"qualified_id": "b", "type": "float", "value": 3.0},
                "2": {"qualified_id": "sum", "type": "add_pair"},
            },
            {"0": edge("0", "2", 0), "1": edge("1", "2", 1)},
            status,
        )

        executor.execute()

        assert {path.name for path in status.iterdir()} == {
            f"a{RUNNING}",
            f"a{SUCCEEDED}",
            f"b{RUNNING}",
            f"b{SUCCEEDED}",
            f"sum{RUNNING}",
            f"sum{SUCCEEDED}",
        }

    def test_a_failing_node_is_marked_failed_and_nothing_after_it_runs(
        self, write_graph, specimen_plugins, tmp_path
    ):
        """GIVEN a graph whose division node divides by zero, with a sink downstream of it
        WHEN it is executed
        THEN that node has .running and .failed but no .succeeded, the sink has no marker at all,
             and the original exception reaches the caller untouched."""
        status = tmp_path / "status"
        executor = self._executor(
            write_graph,
            {
                "0": {"qualified_id": "num", "type": "float", "value": 1.0},
                "1": {"qualified_id": "zero", "type": "float", "value": 0.0},
                "2": {"qualified_id": "div", "type": "specimen.ratio"},
                "3": {"qualified_id": "sink", "type": "anything"},
            },
            {"0": edge("0", "2", 0), "1": edge("1", "2", 1), "2": edge("2", "3", 0)},
            status,
        )

        with pytest.raises(ZeroDivisionError):
            executor.execute()

        names = {path.name for path in status.iterdir()}
        assert f"div{RUNNING}" in names
        assert f"div{FAILED}" in names
        assert f"div{SUCCEEDED}" not in names
        assert not [name for name in names if name.startswith("sink")]

    def test_a_graph_that_fails_validation_leaves_an_empty_directory(
        self, write_graph, specimen_plugins, tmp_path
    ):
        """GIVEN a status directory holding a marker from an earlier job, and an invalid graph
        WHEN the executor is constructed and raises
        THEN the directory exists and is empty.

        The platform then sees "nothing has run yet" rather than the previous job's timeline read
        as this one's. That is what preparing the directory on the first line of __init__ buys —
        before the graph is read, and before any plugin is loaded."""
        status = tmp_path / "status"
        status.mkdir()
        (status / f"old{SUCCEEDED}").touch()

        with pytest.raises(ValueError):
            self._executor(write_graph, {"0": {"type": "no_such_node"}}, {}, status)

        assert status.is_dir()
        assert list(status.iterdir()) == []
