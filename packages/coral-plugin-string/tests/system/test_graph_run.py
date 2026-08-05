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
GRAPH = {
    "workflow": {
        "nodes": {
            "prefix": {"type": "str", "value": "Hello, "},
            "text": {"type": "str", "value": "world"},
            "sp": {"type": "StringProcessor"},
            "cat": {"type": "StringProcessor.concatenate"},
            "out": {"type": "print_text"},
        },
        "edges": {
            # the prefix feeds the constructor
            "e0": {"source": "prefix", "target": "sp", "source_output": 0, "target_input": 0},
            # the instance is the method's port 0; the text is port 1
            "e1": {"source": "sp", "target": "cat", "source_output": 0, "target_input": 0},
            "e2": {"source": "text", "target": "cat", "source_output": 0, "target_input": 1},
            # the concatenation feeds the printer
            "e3": {"source": "cat", "target": "out", "source_output": 0, "target_input": 0},
        },
    }
}


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
        assert results["prefix"] == "Hello, "
        assert results["text"] == "world"

    def test_the_constructor_holds_the_prefix(self, results):
        """GIVEN the prefix wired into StringProcessor's only input
        WHEN the graph is executed
        THEN the constructor node holds an instance carrying it."""
        assert isinstance(results["sp"], StringProcessor)
        assert results["sp"].prefix == "Hello, "

    def test_the_method_node_concatenates(self, results):
        """GIVEN the instance on port 0 and the text on port 1
        WHEN the graph is executed
        THEN the method node holds the concatenation, in prefix-then-text order.

        The port order is the assertion: swapped, this would be "worldHello, "."""
        assert results["cat"] == "Hello, world"

    def test_the_printer_returns_none(self, results):
        """GIVEN print_text at the end
        WHEN the graph is executed
        THEN its result is None — it has no outputs, so nothing may follow it."""
        assert results["out"] is None

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
