"""
Tests for the WorkflowExecutor core functionality - corrected workflow format.
"""

from typing import Any, Tuple

import pytest
from coral_app.executor import WorkflowExecutor
from coral_app.nodestatus import FAILED, RUNNING, STATUS_SUFFIXES, SUCCEEDED


class TestWorkflowExecutorInitialization:
    """Test WorkflowExecutor initialization and setup."""

    @pytest.mark.math
    def test_executor_with_file_path(self, workflow_files):
        """Test executor initialization with file path.

        The nodes and edges now live on the validated graph the executor holds, not on the executor
        itself.
        """
        executor = WorkflowExecutor(str(workflow_files["math"]), plugins=["math"])
        assert executor.graph.nodes
        assert executor.graph.edges

    @pytest.mark.math
    @pytest.mark.string
    def test_executor_loads_multiple_plugins(self, workflow_files):
        """Test executor can load multiple plugins."""
        executor = WorkflowExecutor(str(workflow_files["math"]), plugins=["math", "string"])
        # Should have both math and string functions
        assert "add" in executor.function_map
        assert "StringProcessor" in executor.class_map


class TestPrimitiveNodeExecution:
    """Test execution of primitive nodes."""

    def test_int_primitive(self, temp_workflow_file):
        """Test integer primitive node execution."""
        workflow = {
            "workflow": {
                "nodes": {
                    "n1": {
                        "qualified_id": "0",
                        "node_type": "primitive",
                        "type": "int",
                        "value": 42,
                    }
                },
                "edges": {},
            }
        }
        file_path = temp_workflow_file(workflow)
        executor = WorkflowExecutor(str(file_path), plugins=[])
        results = executor.execute()

        assert "n1" in results
        assert results["n1"] == 42
        assert isinstance(results["n1"], int)

    def test_float_primitive(self, temp_workflow_file):
        """Test float primitive node execution."""
        workflow = {
            "workflow": {
                "nodes": {
                    "n1": {
                        "qualified_id": "0",
                        "node_type": "primitive",
                        "type": "float",
                        "value": 3.14,
                    }
                },
                "edges": {},
            }
        }
        file_path = temp_workflow_file(workflow)
        executor = WorkflowExecutor(str(file_path), plugins=[])
        results = executor.execute()

        assert "n1" in results
        assert results["n1"] == 3.14
        assert isinstance(results["n1"], float)

    def test_string_primitive(self, temp_workflow_file):
        """Test string primitive node execution."""
        workflow = {
            "workflow": {
                "nodes": {
                    "n1": {
                        "qualified_id": "0",
                        "node_type": "primitive",
                        "type": "str",
                        "value": "hello",
                    }
                },
                "edges": {},
            }
        }
        file_path = temp_workflow_file(workflow)
        executor = WorkflowExecutor(str(file_path), plugins=[])
        results = executor.execute()

        assert "n1" in results
        assert results["n1"] == "hello"
        assert isinstance(results["n1"], str)

    def test_bool_primitive(self, temp_workflow_file):
        """Test boolean primitive node execution."""
        workflow = {
            "workflow": {
                "nodes": {
                    "n1": {
                        "qualified_id": "0",
                        "node_type": "primitive",
                        "type": "bool",
                        "value": True,
                    }
                },
                "edges": {},
            }
        }
        file_path = temp_workflow_file(workflow)
        executor = WorkflowExecutor(str(file_path), plugins=[])
        results = executor.execute()

        assert "n1" in results
        assert results["n1"] is True
        assert isinstance(results["n1"], bool)


class TestFunctionNodeExecution:
    """Test execution of function nodes."""

    pytestmark = pytest.mark.math

    def test_simple_add_function(self, temp_workflow_file):
        """Test simple addition function execution."""
        workflow = {
            "workflow": {
                "nodes": {
                    "n1": {
                        "qualified_id": "0",
                        "node_type": "primitive",
                        "type": "float",
                        "value": 5.0,
                    },
                    "n2": {
                        "qualified_id": "1",
                        "node_type": "primitive",
                        "type": "float",
                        "value": 3.0,
                    },
                    "n3": {"qualified_id": "2", "type": "add"},
                },
                "edges": {
                    "e1": {"source": "n1", "target": "n3", "source_output": 0, "target_input": 0},
                    "e2": {"source": "n2", "target": "n3", "source_output": 0, "target_input": 1},
                },
            }
        }
        file_path = temp_workflow_file(workflow)
        executor = WorkflowExecutor(str(file_path), plugins=["math"])
        results = executor.execute()

        assert "n3" in results
        assert results["n3"] == 8.0

    def test_multiply_function(self, temp_workflow_file):
        """Test multiplication function execution."""
        workflow = {
            "workflow": {
                "nodes": {
                    "n1": {
                        "qualified_id": "0",
                        "node_type": "primitive",
                        "type": "float",
                        "value": 4.0,
                    },
                    "n2": {
                        "qualified_id": "1",
                        "node_type": "primitive",
                        "type": "float",
                        "value": 2.5,
                    },
                    "n3": {"qualified_id": "2", "type": "multiply"},
                },
                "edges": {
                    "e1": {"source": "n1", "target": "n3", "source_output": 0, "target_input": 0},
                    "e2": {"source": "n2", "target": "n3", "source_output": 0, "target_input": 1},
                },
            }
        }
        file_path = temp_workflow_file(workflow)
        executor = WorkflowExecutor(str(file_path), plugins=["math"])
        results = executor.execute()

        assert "n3" in results
        assert results["n3"] == 10.0

    def test_chained_functions(self, temp_workflow_file):
        """Test chained function execution."""
        workflow = {
            "workflow": {
                "nodes": {
                    "n1": {
                        "qualified_id": "0",
                        "node_type": "primitive",
                        "type": "float",
                        "value": 2.0,
                    },
                    "n2": {
                        "qualified_id": "1",
                        "node_type": "primitive",
                        "type": "float",
                        "value": 3.0,
                    },
                    "n3": {"qualified_id": "2", "type": "add"},
                    "n4": {
                        "qualified_id": "3",
                        "node_type": "primitive",
                        "type": "float",
                        "value": 2.0,
                    },
                    "n5": {"qualified_id": "4", "type": "multiply"},
                },
                "edges": {
                    "e1": {"source": "n1", "target": "n3", "source_output": 0, "target_input": 0},
                    "e2": {"source": "n2", "target": "n3", "source_output": 0, "target_input": 1},
                    "e3": {"source": "n3", "target": "n5", "source_output": 0, "target_input": 0},
                    "e4": {"source": "n4", "target": "n5", "source_output": 0, "target_input": 1},
                },
            }
        }
        file_path = temp_workflow_file(workflow)
        executor = WorkflowExecutor(str(file_path), plugins=["math"])
        results = executor.execute()

        assert "n3" in results
        assert results["n3"] == 5.0  # 2 + 3
        assert "n5" in results
        assert results["n5"] == 10.0  # 5 * 2


class TestConstructorNodeExecution:
    """Test execution of constructor nodes."""

    pytestmark = pytest.mark.math

    def test_calculator_constructor(self, temp_workflow_file):
        """Test Calculator class instantiation."""
        workflow = {
            "workflow": {
                "nodes": {
                    "n1": {
                        "qualified_id": "0",
                        "node_type": "primitive",
                        "type": "float",
                        "value": 10.0,
                    },
                    "n2": {"qualified_id": "1", "node_type": "constructor", "type": "Calculator"},
                },
                "edges": {
                    "e1": {"source": "n1", "target": "n2", "source_output": 0, "target_input": 0}
                },
            }
        }
        file_path = temp_workflow_file(workflow)
        executor = WorkflowExecutor(str(file_path), plugins=["math"])
        results = executor.execute()

        assert "n2" in results
        # Check it's a Calculator instance
        assert hasattr(results["n2"], "value")
        assert results["n2"].value == 10.0


class TestMethodNodeExecution:
    """Test execution of method nodes."""

    pytestmark = pytest.mark.math

    def test_calculator_method(self, temp_workflow_file):
        """Test Calculator method execution."""
        workflow = {
            "workflow": {
                "nodes": {
                    "n1": {
                        "qualified_id": "0",
                        "node_type": "primitive",
                        "type": "float",
                        "value": 10.0,
                    },
                    "n2": {"qualified_id": "1", "node_type": "constructor", "type": "Calculator"},
                    "n3": {
                        "qualified_id": "2",
                        "node_type": "primitive",
                        "type": "float",
                        "value": 5.0,
                    },
                    "n4": {"qualified_id": "3", "type": "Calculator.add_to_value"},
                },
                "edges": {
                    "e1": {"source": "n1", "target": "n2", "source_output": 0, "target_input": 0},
                    "e2": {"source": "n2", "target": "n4", "source_output": -1, "target_input": 0},
                    "e3": {"source": "n3", "target": "n4", "source_output": 0, "target_input": 1},
                },
            }
        }
        file_path = temp_workflow_file(workflow)
        executor = WorkflowExecutor(str(file_path), plugins=["math"])
        results = executor.execute()

        assert "n4" in results
        assert results["n4"] == 15.0  # 10 + 5


class TestTopologicalSorting:
    """Test topological sorting and execution order."""

    pytestmark = pytest.mark.math

    def test_simple_dag(self, temp_workflow_file):
        """Test topological sort on simple DAG."""
        workflow = {
            "workflow": {
                "nodes": {
                    "n1": {
                        "qualified_id": "0",
                        "node_type": "primitive",
                        "type": "int",
                        "value": 1,
                    },
                    "n2": {
                        "qualified_id": "1",
                        "node_type": "primitive",
                        "type": "int",
                        "value": 2,
                    },
                    "n3": {"qualified_id": "2", "type": "add"},
                },
                "edges": {
                    "e1": {"source": "n1", "target": "n3", "source_output": 0, "target_input": 0},
                    "e2": {"source": "n2", "target": "n3", "source_output": 0, "target_input": 1},
                },
            }
        }
        file_path = temp_workflow_file(workflow)
        executor = WorkflowExecutor(str(file_path), plugins=["math"])
        execution_order = executor.graph.order

        # n3 should come after n1 and n2
        n1_idx = execution_order.index("n1")
        n2_idx = execution_order.index("n2")
        n3_idx = execution_order.index("n3")

        assert n1_idx < n3_idx
        assert n2_idx < n3_idx

    def test_parallel_edges_to_one_node(self, temp_workflow_file):
        """GIVEN one primitive wired into both ports of a single `add` node
        WHEN the execution order is computed
        THEN both nodes appear exactly once, the primitive first."""
        workflow = {
            "workflow": {
                "nodes": {
                    "n1": {"qualified_id": "0", "type": "float", "value": 4.0},
                    "n2": {"qualified_id": "1", "type": "add"},
                },
                "edges": {
                    "e1": {"source": "n1", "target": "n2", "source_output": 0, "target_input": 0},
                    "e2": {"source": "n1", "target": "n2", "source_output": 0, "target_input": 1},
                },
            }
        }
        file_path = temp_workflow_file(workflow)
        executor = WorkflowExecutor(str(file_path), plugins=["math"])
        order = executor.graph.order

        assert order.count("n1") == 1
        assert order.count("n2") == 1
        assert order.index("n1") < order.index("n2")

    def test_diamond(self, temp_workflow_file):
        """GIVEN a diamond — one source feeding two branches that rejoin at one sink
        WHEN the execution order is computed
        THEN every node appears once, after all of its predecessors."""
        workflow = {
            "workflow": {
                "nodes": {
                    "src": {"qualified_id": "0", "type": "float", "value": 9.0},
                    "left": {"qualified_id": "1", "type": "math.sqrt"},
                    "right": {"qualified_id": "2", "type": "math.sin"},
                    "sink": {"qualified_id": "3", "type": "add"},
                },
                "edges": {
                    "e1": {
                        "source": "src",
                        "target": "left",
                        "source_output": 0,
                        "target_input": 0,
                    },
                    "e2": {
                        "source": "src",
                        "target": "right",
                        "source_output": 0,
                        "target_input": 0,
                    },
                    "e3": {
                        "source": "left",
                        "target": "sink",
                        "source_output": 0,
                        "target_input": 0,
                    },
                    "e4": {
                        "source": "right",
                        "target": "sink",
                        "source_output": 0,
                        "target_input": 1,
                    },
                },
            }
        }
        file_path = temp_workflow_file(workflow)
        executor = WorkflowExecutor(str(file_path), plugins=["math"])
        order = executor.graph.order

        assert sorted(order) == ["left", "right", "sink", "src"]
        assert order.index("src") < order.index("left") < order.index("sink")
        assert order.index("src") < order.index("right") < order.index("sink")

    def test_isolated_node(self, temp_workflow_file):
        """GIVEN a graph holding a connected pair plus a node with no edges at all
        WHEN the execution order is computed
        THEN the isolated node is still scheduled, alongside the connected ones."""
        workflow = {
            "workflow": {
                "nodes": {
                    "n1": {"qualified_id": "0", "type": "float", "value": 16.0},
                    "n2": {"qualified_id": "1", "type": "math.sqrt"},
                    "lonely": {"qualified_id": "2", "type": "str", "value": "unconnected"},
                },
                "edges": {
                    "e1": {"source": "n1", "target": "n2", "source_output": 0, "target_input": 0},
                },
            }
        }
        file_path = temp_workflow_file(workflow)
        executor = WorkflowExecutor(str(file_path), plugins=["math"])
        order = executor.graph.order

        assert sorted(order) == ["lonely", "n1", "n2"]
        assert order.index("n1") < order.index("n2")

    def test_empty_graph(self, temp_workflow_file):
        """GIVEN a workflow with no nodes and no edges
        WHEN the execution order is computed
        THEN it is empty, and no error is raised."""
        workflow = {"workflow": {"nodes": {}, "edges": {}}}
        file_path = temp_workflow_file(workflow)
        executor = WorkflowExecutor(str(file_path), plugins=["math"])

        assert executor.graph.order == []

    def test_cycle_detection(self, circular_workflow_dict, temp_workflow_file):
        """Test that circular dependencies are detected.

        Validation now happens while the executor is constructed, so the cycle is caught before any
        node runs rather than on a later call.
        """
        file_path = temp_workflow_file(circular_workflow_dict)

        with pytest.raises(ValueError, match="Cycle detected"):
            WorkflowExecutor(str(file_path), plugins=["math"])


class TestEdgeOrdering:
    """Test that edge target_input ordering is respected."""

    pytestmark = pytest.mark.math

    def test_input_order_matters(self, temp_workflow_file):
        """Test that parameter order follows target_input values."""
        # math.pow(x, y) = x^y, so order matters
        workflow = {
            "workflow": {
                "nodes": {
                    "n1": {
                        "qualified_id": "0",
                        "node_type": "primitive",
                        "type": "float",
                        "value": 2.0,
                    },
                    "n2": {
                        "qualified_id": "1",
                        "node_type": "primitive",
                        "type": "float",
                        "value": 3.0,
                    },
                    "n3": {"qualified_id": "2", "type": "math.pow"},
                },
                "edges": {
                    "e1": {"source": "n1", "target": "n3", "source_output": 0, "target_input": 0},
                    "e2": {"source": "n2", "target": "n3", "source_output": 0, "target_input": 1},
                },
            }
        }
        file_path = temp_workflow_file(workflow)
        executor = WorkflowExecutor(str(file_path), plugins=["math"])
        results = executor.execute()

        assert "n3" in results
        assert results["n3"] == 8.0  # 2^3 = 8, not 3^2 = 9


def pair() -> tuple:
    """One output port, whose value happens to be a tuple."""
    return (10, 20)


def triple() -> Tuple[Any, Any, Any]:
    """Three output ports, bundled into one returned tuple."""
    return (10, 20, 30)


def sink(x: Any) -> Any:
    """Records whatever arrives on its single input port."""
    return x


def short_triple() -> Tuple[Any, Any, Any]:
    """Declares three outputs but returns only two — an over-declaring annotation."""
    return (10, 20)


def long_pair() -> Tuple[Any, Any]:
    """Declares two outputs but returns three — an under-declaring annotation."""
    return (10, 20, 30)


def not_a_tuple() -> Tuple[Any, Any]:
    """Declares two outputs but returns something that is not a bundle at all."""
    return 10


@pytest.fixture
def executor_over(temp_workflow_file, monkeypatch):
    """Build a real ``WorkflowExecutor`` over an ad-hoc function map.

    The node types these tests need are deliberately not in any plugin, so the map is injected by
    monkeypatching the executor's own ``build_function_map``. Everything else is production code:
    ``__init__`` still builds the port table and constructs (hence validates) the ``Graph``, which
    matters because that is the path output-port resolution fails in.
    """

    def _build(function_map, nodes, edges):
        monkeypatch.setattr(
            "coral_app.executor.build_function_map", lambda **kwargs: dict(function_map)
        )
        workflow = {"workflow": {"nodes": nodes, "edges": edges}}
        return WorkflowExecutor(str(temp_workflow_file(workflow)), plugins=[])

    return _build


class TestOutputPortResolution:
    """Which value an edge carries is decided by the port table, not by the value."""

    FUNCTIONS = {"pair": pair, "triple": triple, "sink": sink}

    def _received(self, executor_over, source, **edge_extras):
        """What ``sink`` is handed, over a graph the ``Graph`` accepted as valid."""
        executor = executor_over(
            self.FUNCTIONS,
            {
                "n1": {"qualified_id": "0", "type": source},
                "n2": {"qualified_id": "1", "type": "sink"},
            },
            {"e1": {"source": "n1", "target": "n2", "target_input": 0, **edge_extras}},
        )
        return executor.execute()["n2"]

    @pytest.mark.parametrize(
        "edge_extras",
        [{}, {"source_output": 0}, {"source_output": -1}],
        ids=["omitted", "0", "-1"],
    )
    def test_the_three_spellings_of_the_only_output_agree(self, executor_over, edge_extras):
        """GIVEN a single-output node whose value is a tuple, read by an edge spelling "the only
        output" as an omitted key, as ``0``, and as ``-1``
        WHEN the workflow runs
        THEN all three deliver the whole tuple.

        Graph check 5 documents the three as synonyms; before the fix they produced ``(10, 20)``,
        ``10`` and ``20`` respectively, because the executor indexed on ``isinstance(value, tuple)``
        instead of asking the port table."""
        assert self._received(executor_over, "pair", **edge_extras) == (10, 20)

    @pytest.mark.parametrize("port, expected", [(0, 10), (1, 20), (2, 30)])
    def test_a_multi_output_node_is_still_indexed(self, executor_over, port, expected):
        """GIVEN a node declaring three outputs and returning a tuple of three
        WHEN each port is read in turn
        THEN each edge carries its own element — the bundle is still unpacked."""
        assert self._received(executor_over, "triple", source_output=port) == expected


class TestOutputArity:
    """A node's declared output count is confronted with what it returned."""

    FUNCTIONS = {
        "short_triple": short_triple,
        "long_pair": long_pair,
        "not_a_tuple": not_a_tuple,
        "sink": sink,
    }

    def _run(self, executor_over, source, edges):
        executor = executor_over(
            self.FUNCTIONS,
            {
                "n1": {"qualified_id": "0", "type": source},
                "n2": {"qualified_id": "1", "type": "sink"},
            },
            edges,
        )
        return executor.execute()

    def _wire(self, port):
        return {"e1": {"source": "n1", "target": "n2", "source_output": port, "target_input": 0}}

    @pytest.mark.parametrize("port", [0, 1, 2], ids=["port-0", "port-1", "port-2"])
    def test_a_short_tuple_raises_whichever_port_is_read(self, executor_over, port):
        """GIVEN a node declaring three outputs that returns a tuple of two
        WHEN the workflow runs
        THEN it raises ValueError at the producing node, no matter which port the consumer reads.

        Before the fix, reading port 2 fell past the ``< len(value)`` bound and delivered the whole
        ``(10, 20)`` bundle silently; ports 0 and 1 gave the right answer and hid the mismatch."""
        with pytest.raises(ValueError, match="declares 3 outputs but returned a tuple of 2"):
            self._run(executor_over, "short_triple", self._wire(port))

    def test_a_short_tuple_raises_even_with_no_consumer(self, executor_over):
        """GIVEN the same node with none of its outputs wired to anything
        WHEN the workflow runs
        THEN it still raises — the check sits at the producer, so a mismatch cannot hide behind an
        unread port."""
        executor = executor_over(
            self.FUNCTIONS, {"n1": {"qualified_id": "0", "type": "short_triple"}}, {}
        )

        with pytest.raises(ValueError, match="declares 3 outputs but returned a tuple of 2"):
            executor.execute()

    def test_a_long_tuple_raises(self, executor_over):
        """GIVEN a node declaring two outputs that returns a tuple of three
        WHEN the workflow runs
        THEN it raises, rather than silently dropping the undeclared element."""
        with pytest.raises(ValueError, match="declares 2 outputs but returned a tuple of 3"):
            self._run(executor_over, "long_pair", self._wire(0))

    def test_a_non_tuple_result_raises_naming_its_type(self, executor_over):
        """GIVEN a node declaring two outputs that returns a bare int
        WHEN the workflow runs
        THEN it raises, naming what came back instead of a bundle."""
        with pytest.raises(ValueError, match="declares 2 outputs but returned int"):
            self._run(executor_over, "not_a_tuple", self._wire(0))

    def test_the_message_names_the_node_and_its_type(self, executor_over):
        """GIVEN any such mismatch
        WHEN it is reported
        THEN the message carries the node id and the node type, so the offending annotation can be
        found from the error alone."""
        with pytest.raises(ValueError, match=r"Node n1 \(short_triple\)"):
            self._run(executor_over, "short_triple", self._wire(0))

    def test_a_matching_multi_output_node_is_untouched(self, executor_over):
        """GIVEN a node whose returned tuple matches its declared three outputs
        WHEN the workflow runs
        THEN nothing is raised and the ports carry their elements — the check is a guard, not a
        new restriction on well-annotated nodes."""
        executor = executor_over(
            {"triple": triple, "sink": sink},
            {
                "n1": {"qualified_id": "0", "type": "triple"},
                "n2": {"qualified_id": "1", "type": "sink"},
            },
            self._wire(1),
        )

        assert executor.execute()["n2"] == 20

    def test_a_single_output_node_returning_a_tuple_is_not_checked(self, executor_over):
        """GIVEN a node declaring one output whose value is a tuple
        WHEN the workflow runs
        THEN nothing is raised — at n == 1 a returned tuple is legitimate and there is nothing to
        compare it against."""
        executor = executor_over(
            {"pair": pair, "sink": sink},
            {
                "n1": {"qualified_id": "0", "type": "pair"},
                "n2": {"qualified_id": "1", "type": "sink"},
            },
            {"e1": {"source": "n1", "target": "n2", "source_output": 0, "target_input": 0}},
        )

        assert executor.execute()["n2"] == (10, 20)


class TestNodeStatusMarkers:
    """The executor's side of the status markers: every node bracketed, and the walk stopped where it
    broke.

    These graphs use only the host's builtin collection nodes, so they run with ``plugins=[]`` —
    what is under test is the walk, not any plugin.
    """

    SUCCEEDING = {
        "nodes": {
            "0": {"qualified_id": "0", "type": "list_new"},
            "1": {"qualified_id": "1", "type": "int", "value": 7},
            "2": {"qualified_id": "2", "type": "list_append"},
            "3": {"qualified_id": "3", "type": "list_size"},
        },
        "edges": {
            "e0": {"source": "0", "target": "2", "source_output": 0, "target_input": 0},
            "e1": {"source": "1", "target": "2", "source_output": 0, "target_input": 1},
            "e2": {"source": "2", "target": "3", "source_output": 0, "target_input": 0},
        },
    }

    # `list_get` on an empty list raises IndexError at node 2, so node 3 never runs.
    FAILING = {
        "nodes": {
            "0": {"qualified_id": "0", "type": "list_new"},
            "1": {"qualified_id": "1", "type": "int", "value": 5},
            "2": {"qualified_id": "2", "type": "list_get"},
            "3": {"qualified_id": "3", "type": "list_size"},
        },
        "edges": {
            "e0": {"source": "0", "target": "2", "source_output": 0, "target_input": 0},
            "e1": {"source": "1", "target": "2", "source_output": 0, "target_input": 1},
            "e2": {"source": "2", "target": "3", "source_output": 0, "target_input": 0},
        },
    }

    def _executor(self, temp_workflow_file, workflow, status_dir):
        return WorkflowExecutor(
            str(temp_workflow_file({"workflow": workflow})),
            plugins=[],
            touch_dir=str(status_dir) if status_dir else None,
        )

    def _markers(self, status_dir, executor, node_id):
        """The suffixes written for one node, by its qualified id."""
        qualified_id = executor.qualified_ids[node_id]
        return {
            path.name[len(qualified_id) :]
            for path in status_dir.iterdir()
            if path.name.startswith(qualified_id)
        }

    def test_every_node_that_ran_is_marked_succeeded(self, temp_workflow_file, tmp_path):
        """GIVEN a graph of four nodes, one of them a primitive, run with a touch directory
        WHEN it completes
        THEN each node has both its markers — primitives included, since the reference backend makes
        every node a task and a graph whose primitives never appear would read as "half the nodes
        never started"."""
        status_dir = tmp_path / "status"
        executor = self._executor(temp_workflow_file, self.SUCCEEDING, status_dir)

        executor.execute()

        for node_id in ("0", "1", "2", "3"):
            assert self._markers(status_dir, executor, node_id) == {RUNNING, SUCCEEDED}

    def test_a_failing_node_is_marked_and_the_walk_stops_there(self, temp_workflow_file, tmp_path):
        """GIVEN a graph whose third node raises
        WHEN it is executed
        THEN the culprit carries ``.running`` and ``.failed`` and no ``.succeeded``, the nodes
        before it are marked succeeded, and the node after it left nothing at all — the directory
        alone says how far the run got and which node stopped it."""
        status_dir = tmp_path / "status"
        executor = self._executor(temp_workflow_file, self.FAILING, status_dir)

        with pytest.raises(IndexError):
            executor.execute()

        assert self._markers(status_dir, executor, "0") == {RUNNING, SUCCEEDED}
        assert self._markers(status_dir, executor, "1") == {RUNNING, SUCCEEDED}
        assert self._markers(status_dir, executor, "2") == {RUNNING, FAILED}
        assert self._markers(status_dir, executor, "3") == set()

    def test_no_touch_dir_writes_nothing(self, temp_workflow_file, tmp_path):
        """GIVEN the same graph run with ``touch_dir=None``
        WHEN it completes
        THEN not one marker exists anywhere below the working directory.

        ``WorkflowExecutor`` is a library object: the reference default of the cwd belongs to the
        CLI, which is where the platform's contract lives."""
        executor = self._executor(temp_workflow_file, self.SUCCEEDING, None)

        executor.execute()

        assert executor.status is None
        assert not [path for path in tmp_path.rglob("*") if path.name.endswith(STATUS_SUFFIXES)]

    def test_a_graph_that_fails_validation_leaves_an_empty_directory(
        self, temp_workflow_file, tmp_path
    ):
        """GIVEN a status directory holding markers from an earlier job, and an invalid graph
        WHEN the executor is constructed and raises
        THEN the directory exists and is empty: the platform sees "nothing has run yet" rather than
        the stale timeline of the previous job. This is why the directory is prepared on the first
        line of ``__init__``, before validation."""
        status_dir = tmp_path / "status"
        status_dir.mkdir()
        (status_dir / f"old{SUCCEEDED}").touch()
        invalid = {"nodes": {"0": {"qualified_id": "0", "type": "no_such_node_type"}}, "edges": {}}

        with pytest.raises(ValueError):
            self._executor(temp_workflow_file, invalid, status_dir)

        assert status_dir.is_dir()
        assert list(status_dir.iterdir()) == []

    def test_a_duplicate_qualified_id_is_rejected_without_a_touch_dir(
        self, temp_workflow_file, tmp_path
    ):
        """GIVEN two nodes declaring the same qualified_id, and no touch directory
        WHEN the executor is constructed
        THEN ValueError names the id — a graph must not become valid or invalid depending on
        whether markers happen to be written."""
        workflow = {
            "nodes": {
                "0": {"type": "int", "value": 1, "qualified_id": "same"},
                "1": {"type": "int", "value": 2, "qualified_id": "same"},
            },
            "edges": {},
        }

        with pytest.raises(ValueError, match="'same'"):
            self._executor(temp_workflow_file, workflow, None)

    def test_a_missing_qualified_id_is_rejected_without_a_touch_dir(
        self, temp_workflow_file, tmp_path
    ):
        """GIVEN a node declaring no qualified_id, and no touch directory
        WHEN the executor is constructed
        THEN ValueError names the node — for the same reason as the duplicate above: the mapping is
        built whether or not markers are written."""
        workflow = {
            "nodes": {
                "0": {"type": "int", "value": 1, "qualified_id": "0"},
                "1": {"type": "int", "value": 2},
            },
            "edges": {},
        }

        with pytest.raises(ValueError, match="'1' declares no qualified_id"):
            self._executor(temp_workflow_file, workflow, None)

    def test_declared_qualified_ids_name_the_files(self, temp_workflow_file, tmp_path):
        """GIVEN nodes whose qualified ids are not their node ids
        WHEN the graph runs with a touch directory
        THEN the markers are named after the qualified ids — on the platform that string is the
        node's path through nested subgraphs, and node ids are unique only within one graph."""
        status_dir = tmp_path / "status"
        workflow = {
            "nodes": {
                "0": {"type": "int", "value": 1, "qualified_id": "7_1"},
                "1": {"type": "int", "value": 2, "qualified_id": "7_2"},
            },
            "edges": {},
        }

        self._executor(temp_workflow_file, workflow, status_dir).execute()

        assert sorted(path.name for path in status_dir.iterdir()) == [
            f"7_1{RUNNING}",
            f"7_1{SUCCEEDED}",
            f"7_2{RUNNING}",
            f"7_2{SUCCEEDED}",
        ]
