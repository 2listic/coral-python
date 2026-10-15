"""This plugin's nodes driven through the host, as a graph.

The graph is written here rather than shipped as a file, because no editor export uses this plugin: it
is the one case where the wiring exists only for the test. Every other plugin discovers its graphs from
its own ``graphs/`` directory.

A characterization test: it pins the executor's results and stdout for one string graph, as the math
suite does for its own. The node type is ``print_text``, this plugin's own name for what it prints.
"""

import pytest
from coral_app.executor import WorkflowExecutor
from coral_plugin_string import StringProcessor
from string_suite import PLUGIN_NAME, node_named

#: Hello-world through this plugin: a prefix and a text into StringProcessor, then printed.
#:
#: The protocol keys nodes by integer, so the ids carry no meaning; each node's ``name`` carries
#: the role it plays, and the assertions look nodes up by it.
GRAPH = {
    "workflow": {
        "nodes": {
            "0": {"qualified_id": "0", "type": "str", "value": "Hello, ", "name": "prefix"},
            "1": {"qualified_id": "1", "type": "str", "value": "world", "name": "text"},
            "2": {"qualified_id": "2", "type": "StringProcessor", "name": "sp"},
            "3": {"qualified_id": "3", "type": "StringProcessor.concatenate", "name": "cat"},
            "4": {"qualified_id": "4", "type": "print_text", "name": "out"},
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


class TestTheStringGraph:
    """Constructor, method and printer, wired together and executed."""

    @pytest.fixture
    def result(self, write_graph):
        """Execute the graph with this plugin selected, returning a lookup from a node's ``name``
        to its result."""
        path = write_graph(GRAPH)
        executor = WorkflowExecutor(str(path), plugins=[PLUGIN_NAME])
        executor.execute()
        return lambda name: executor.results[node_named(executor.graph, name)]

    def test_the_primitives_carry_their_strings(self, result):
        """GIVEN two `str` primitives
        WHEN the graph is executed
        THEN each holds its literal, whitespace included."""
        assert result("prefix") == "Hello, "
        assert result("text") == "world"

    def test_the_constructor_holds_the_prefix(self, result):
        """GIVEN the prefix wired into StringProcessor's only input
        WHEN the graph is executed
        THEN the constructor node holds an instance carrying it."""
        assert isinstance(result("sp"), StringProcessor)
        assert result("sp").prefix == "Hello, "

    def test_the_method_node_concatenates(self, result):
        """GIVEN the instance on port 0 and the text on port 1
        WHEN the graph is executed
        THEN the method node holds the concatenation, in prefix-then-text order.

        The port order is the assertion: swapped, this would be "worldHello, "."""
        assert result("cat") == "Hello, world"

    def test_the_printer_returns_none(self, result):
        """GIVEN print_text at the end
        WHEN the graph is executed
        THEN its result is None — it has no outputs, so nothing may follow it."""
        assert result("out") is None

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
