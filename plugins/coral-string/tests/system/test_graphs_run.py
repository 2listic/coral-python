"""This plugin's nodes driven through the host, as a graph.

The graph is written here rather than shipped as a file, because no editor export uses this plugin: it
is the one case where the wiring exists only for the test. Every other plugin discovers its graphs from
its own ``graphs/`` directory.

Inherited from the characterization test written for issue #16, which pinned the executor's results and
stdout for one math graph and one string graph before the plugin-modularization move. The math half now
lives in math's suite against its real exports; this is the string half, rehomed and with the node type
updated to ``print_text``.
"""

import pytest
from coral_app.executor import WorkflowExecutor
from coral_plugin_string import StringProcessor
from string_suite import PLUGIN_NAME

#: Hello-world through this plugin: a prefix and a text into StringProcessor, then printed.
#:
#: The protocol keys nodes by integer, so the ids carry no meaning; each node's ``qualified_id``
#: keeps the name it plays, and `NODES` below maps that name back to the id the assertions need.
GRAPH = {
    "workflow": {
        "nodes": {
            "0": {"qualified_id": "prefix", "type": "str", "value": "Hello, "},
            "1": {"qualified_id": "text", "type": "str", "value": "world"},
            "2": {"qualified_id": "sp", "type": "StringProcessor"},
            "3": {"qualified_id": "cat", "type": "StringProcessor.concatenate"},
            "4": {"qualified_id": "out", "type": "print_text"},
        },
        "edges": {
            # the prefix feeds the constructor
            "0": {"source": "0", "target": "2", "source_output": 0, "target_input": 0},
            # the instance is the method's port 0; the text is port 1
            "1": {"source": "2", "target": "3", "source_output": 0, "target_input": 0},
            "2": {"source": "1", "target": "3", "source_output": 0, "target_input": 1},
            # the concatenation feeds the printer
            "3": {"source": "3", "target": "4", "source_output": 0, "target_input": 0},
        },
    }
}

#: Each node of ``GRAPH`` by the name it plays — its ``qualified_id``, which the ids themselves
#: cannot carry. Maintained by hand alongside the graph above: renumber one without the other and
#: the assertions move to the wrong nodes.
NODES = {"prefix": "0", "text": "1", "sp": "2", "cat": "3", "out": "4"}


class TestTheStringGraph:
    """Constructor, method and printer, wired together and executed."""

    @pytest.fixture
    def results(self, write_graph):
        """Execute the graph with this plugin selected."""
        path = write_graph(GRAPH)
        return WorkflowExecutor(str(path), plugins=[PLUGIN_NAME]).execute()

    def test_the_primitives_carry_their_strings(self, results):
        """GIVEN two `str` primitives
        WHEN the graph is executed
        THEN each holds its literal, whitespace included."""
        assert results[NODES["prefix"]] == "Hello, "
        assert results[NODES["text"]] == "world"

    def test_the_constructor_holds_the_prefix(self, results):
        """GIVEN the prefix wired into StringProcessor's only input
        WHEN the graph is executed
        THEN the constructor node holds an instance carrying it."""
        assert isinstance(results[NODES["sp"]], StringProcessor)
        assert results[NODES["sp"]].prefix == "Hello, "

    def test_the_method_node_concatenates(self, results):
        """GIVEN the instance on port 0 and the text on port 1
        WHEN the graph is executed
        THEN the method node holds the concatenation, in prefix-then-text order.

        The port order is the assertion: swapped, this would be "worldHello, "."""
        assert results[NODES["cat"]] == "Hello, world"

    def test_the_printer_returns_none(self, results):
        """GIVEN print_text at the end
        WHEN the graph is executed
        THEN its result is None — it has no outputs, so nothing may follow it."""
        assert results[NODES["out"]] is None

    def test_the_user_visible_output(self, write_graph, capsys):
        """GIVEN the graph
        WHEN it is executed
        THEN the method's line and the printed value both appear in stdout.

        This is what `coral run` shows, and it was the point of the original characterization test:
        results *and* stdout, so a refactor that quietly stopped printing would be caught."""
        path = write_graph(GRAPH)

        WorkflowExecutor(str(path), plugins=[PLUGIN_NAME]).execute()

        out = capsys.readouterr().out
        assert "StringProcessor.concatenate('world') = 'Hello, world'" in out
        assert "Print: Hello, world" in out
