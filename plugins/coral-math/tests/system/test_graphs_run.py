"""This plugin's graphs, executed end to end, with the numbers written down.

The graphs are the same files ``test_graphs_validate.py`` constructs; here they run. Every case
asserts **values**, not that execution "did not raise": three of these were previously executed by
tests that asserted nothing at all, which is a wall-clock cost with no failure mode.

Three files are real editor exports and one is the collections/math interop graph. Their arithmetic is
this plugin's business, which is why the expected numbers live here rather than in the host's suite.
"""

import math

import pytest
from coral_app.executor import WorkflowExecutor
from math_suite import GRAPHS, PLUGIN_NAME


def run(path):
    """Execute a graph with this plugin selected, returning results keyed by node id."""
    return WorkflowExecutor(str(path), plugins=[PLUGIN_NAME]).execute()


class TestTheMathExport:
    """``network-from-fe-math.json`` — float(2) -> math.sqrt -> math.sin -> print_number."""

    @pytest.fixture(scope="class")
    def results(self):
        return run(GRAPHS / "network-from-fe-math.json")

    def test_the_chain_computes_the_exact_values(self, results):
        """GIVEN the exported math chain
        WHEN it is executed
        THEN each node holds exactly the value its function computes.

        Exact equality, not approximate: the executor passes floats through untouched, so any
        difference here would be a real change in what a user's graph returns."""
        expected_sqrt = math.sqrt(2.0)

        assert results["1"] == 2.0  # the float primitive carries "2" as a string
        assert results["0"] == expected_sqrt
        assert results["2"] == math.sin(expected_sqrt)

    def test_the_terminal_print_node_returns_none(self, results):
        """GIVEN print_number at the end of the chain
        WHEN the graph is executed
        THEN its result is None — it has no outputs, so nothing may be wired after it."""
        assert results["3"] is None

    def test_every_node_produced_a_result(self, results):
        """GIVEN the exported graph
        WHEN it is executed
        THEN every declared node has a result: none was left unvisited."""
        assert set(results) == {"0", "1", "2", "3"}

    def test_the_domain_output_is_printed(self, capsys):
        """GIVEN the exported math chain
        WHEN it is executed
        THEN each function's own line appears in stdout, ending with the printed result.

        This is what a user sees from `coral run`, so it is part of the behaviour, not decoration."""
        expected_sqrt = math.sqrt(2.0)
        expected_sin = math.sin(expected_sqrt)

        run(GRAPHS / "network-from-fe-math.json")

        out = capsys.readouterr().out
        assert f"math.sqrt(2.0) = {expected_sqrt}" in out
        assert f"math.sin({expected_sqrt}) = {expected_sin}" in out
        assert f"Print: {expected_sin}" in out


class TestTheFunctionsExport:
    """``network-from-fe-functions.json`` — (3 + 2) * 4, then printed."""

    @pytest.fixture(scope="class")
    def results(self):
        return run(GRAPHS / "network-from-fe-functions.json")

    def test_the_arithmetic(self, results):
        """GIVEN the exported graph adding 3 and 2 and multiplying by 4
        WHEN it is executed
        THEN the sum is 5.0 and the product is 20.0.

        Previously this graph was executed by a test with **no assertion at all** — it could only
        fail by raising."""
        assert results["3"] == 5.0
        assert results["6"] == 20.0

    def test_the_primitives_are_cast_by_their_declared_type(self, results):
        """GIVEN primitives carrying "3.0", "2" and "4" as strings
        WHEN the graph is executed
        THEN each is a float, because the node's declared type does the casting."""
        assert results["0"] == 3.0
        assert results["2"] == 2.0
        assert results["5"] == 4.0
        assert all(isinstance(results[node], float) for node in ("0", "2", "5"))

    def test_the_print_node_returns_none(self, results):
        """GIVEN print_number fed by the product
        WHEN the graph is executed
        THEN it returns None."""
        assert results["1"] is None


class TestTheClassesExport:
    """``network-from-fe-classes.json`` — a Calculator, mutated twice, then printed."""

    @pytest.fixture(scope="class")
    def results(self):
        return run(GRAPHS / "network-from-fe-classes.json")

    def test_the_constructor_holds_the_primitive(self, results):
        """GIVEN float(2) wired into Calculator's only input
        WHEN the graph is executed
        THEN the constructor node holds a Calculator built from it."""
        from coral_plugin_math import Calculator

        assert isinstance(results["1"], Calculator)

    def test_the_two_methods_compose_on_one_instance(self, results):
        """GIVEN add_to_value(2) feeding multiply_value's factor, both on the same instance
        WHEN the graph is executed
        THEN the results are 4.0 and 16.0.

        `Calculator` is stateful, so the second call sees the first call's mutation: 2 + 2 = 4, then
        4 * 4 = 16, the factor being the first result. Also previously executed with no assertion at
        all."""
        assert results["5"] == 4.0
        assert results["4"] == 16.0

    def test_the_instance_ends_at_the_last_mutation(self, results):
        """GIVEN the same instance shared by both method nodes
        WHEN the graph has finished
        THEN it holds the final value: one object, mutated in execution order."""
        assert results["1"].value == 16.0

    def test_the_print_node_returns_none(self, results):
        """GIVEN print_number fed by the last method
        WHEN the graph is executed
        THEN it returns None."""
        assert results["3"] is None


#: ``network-collections-math.json``'s nodes by the name each one plays. The protocol requires
#: integer node ids, which therefore carry no meaning; the meaning lives here, so the assertions
#: below still read as sentences about the graph rather than about node "6". Every node is listed,
#: not only the asserted ones, so the map doubles as the graph's legend.
#:
#: Nothing ties the map to the file: renumber the graph without updating this and the assertions
#: move to the wrong nodes. Both are hand-maintained together, deliberately — the alternative was a
#: ``"name"`` field the protocol has no room for.
NODES = {
    "three": "0",
    "four": "1",
    "index_0": "2",
    "index_1": "3",
    "empty": "4",
    "with_three": "5",
    "with_both": "6",
    "first": "7",
    "second": "8",
    "total": "9",
}


class TestTheCollectionsInteropGraph:
    """``network-collections-math.json`` — the host's builtins feeding this plugin's ``add``.

    The file is named "collections" but it wires an `add` node, so it is this plugin's: it needs
    `math`, and it lives where its requirement is satisfied. It is the one graph that proves the
    host's builtin nodes and a plugin's nodes interoperate.
    """

    @pytest.fixture(scope="class")
    def results(self):
        return run(GRAPHS / "network-collections-math.json")

    def test_the_list_is_built_by_the_host_builtins(self, results):
        """GIVEN list_new followed by two list_append nodes
        WHEN the graph is executed
        THEN each append returns a *new* list, leaving the previous one untouched.

        The builtins are pure by design: several downstream nodes may read one result, in an order the
        topological sort chooses, so in-place mutation would make the outcome depend on that choice."""
        assert results[NODES["empty"]] == []
        assert results[NODES["with_three"]] == [3.0]
        assert results[NODES["with_both"]] == [3.0, 4.0]

    def test_extraction_feeds_the_plugin_function(self, results):
        """GIVEN two list_get nodes feeding this plugin's add
        WHEN the graph is executed
        THEN the elements come out in index order and their sum is computed by `add`."""
        assert results[NODES["first"]] == 3.0
        assert results[NODES["second"]] == 4.0
        assert results[NODES["total"]] == 7.0
