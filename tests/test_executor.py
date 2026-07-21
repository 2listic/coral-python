"""
Tests for the WorkflowExecutor core functionality - corrected workflow format.
"""

import pytest
from pathlib import Path
from coral_app.executor import WorkflowExecutor


class TestWorkflowExecutorInitialization:
    """Test WorkflowExecutor initialization and setup."""

    def test_executor_with_file_path(self, workflow_files):
        """Test executor initialization with file path."""
        executor = WorkflowExecutor(str(workflow_files["math"]), modules=['math'])
        assert executor.nodes is not None
        assert executor.edges is not None

    def test_executor_loads_multiple_modules(self, workflow_files):
        """Test executor can load multiple modules."""
        executor = WorkflowExecutor(
            str(workflow_files["math"]),
            modules=['math', 'string']
        )
        # Should have both math and string functions
        assert 'add' in executor.function_map
        assert 'StringProcessor' in executor.class_map


class TestPrimitiveNodeExecution:
    """Test execution of primitive nodes."""

    def test_int_primitive(self, temp_workflow_file):
        """Test integer primitive node execution."""
        workflow = {
            "workflow": {
                "nodes": {
                    "n1": {"node_type": "primitive", "type": "int", "value": 42}
                },
                "edges": {}
            }
        }
        file_path = temp_workflow_file(workflow)
        executor = WorkflowExecutor(str(file_path))
        results = executor.execute()

        assert "n1" in results
        assert results["n1"] == 42
        assert isinstance(results["n1"], int)

    def test_float_primitive(self, temp_workflow_file):
        """Test float primitive node execution."""
        workflow = {
            "workflow": {
                "nodes": {
                    "n1": {"node_type": "primitive", "type": "float", "value": 3.14}
                },
                "edges": {}
            }
        }
        file_path = temp_workflow_file(workflow)
        executor = WorkflowExecutor(str(file_path))
        results = executor.execute()

        assert "n1" in results
        assert results["n1"] == 3.14
        assert isinstance(results["n1"], float)

    def test_string_primitive(self, temp_workflow_file):
        """Test string primitive node execution."""
        workflow = {
            "workflow": {
                "nodes": {
                    "n1": {"node_type": "primitive", "type": "str", "value": "hello"}
                },
                "edges": {}
            }
        }
        file_path = temp_workflow_file(workflow)
        executor = WorkflowExecutor(str(file_path))
        results = executor.execute()

        assert "n1" in results
        assert results["n1"] == "hello"
        assert isinstance(results["n1"], str)

    def test_bool_primitive(self, temp_workflow_file):
        """Test boolean primitive node execution."""
        workflow = {
            "workflow": {
                "nodes": {
                    "n1": {"node_type": "primitive", "type": "bool", "value": True}
                },
                "edges": {}
            }
        }
        file_path = temp_workflow_file(workflow)
        executor = WorkflowExecutor(str(file_path))
        results = executor.execute()

        assert "n1" in results
        assert results["n1"] is True
        assert isinstance(results["n1"], bool)


class TestFunctionNodeExecution:
    """Test execution of function nodes."""

    def test_simple_add_function(self, temp_workflow_file):
        """Test simple addition function execution."""
        workflow = {
            "workflow": {
                "nodes": {
                    "n1": {"node_type": "primitive", "type": "float", "value": 5.0},
                    "n2": {"node_type": "primitive", "type": "float", "value": 3.0},
                    "n3": {"type": "add"}
                },
                "edges": {
                    "e1": {"source": "n1", "target": "n3", "source_output": 0, "target_input": 0},
                    "e2": {"source": "n2", "target": "n3", "source_output": 0, "target_input": 1}
                }
            }
        }
        file_path = temp_workflow_file(workflow)
        executor = WorkflowExecutor(str(file_path), modules=['math'])
        results = executor.execute()

        assert "n3" in results
        assert results["n3"] == 8.0

    def test_multiply_function(self, temp_workflow_file):
        """Test multiplication function execution."""
        workflow = {
            "workflow": {
                "nodes": {
                    "n1": {"node_type": "primitive", "type": "float", "value": 4.0},
                    "n2": {"node_type": "primitive", "type": "float", "value": 2.5},
                    "n3": {"type": "multiply"}
                },
                "edges": {
                    "e1": {"source": "n1", "target": "n3", "source_output": 0, "target_input": 0},
                    "e2": {"source": "n2", "target": "n3", "source_output": 0, "target_input": 1}
                }
            }
        }
        file_path = temp_workflow_file(workflow)
        executor = WorkflowExecutor(str(file_path), modules=['math'])
        results = executor.execute()

        assert "n3" in results
        assert results["n3"] == 10.0

    def test_chained_functions(self, temp_workflow_file):
        """Test chained function execution."""
        workflow = {
            "workflow": {
                "nodes": {
                    "n1": {"node_type": "primitive", "type": "float", "value": 2.0},
                    "n2": {"node_type": "primitive", "type": "float", "value": 3.0},
                    "n3": {"type": "add"},
                    "n4": {"node_type": "primitive", "type": "float", "value": 2.0},
                    "n5": {"type": "multiply"}
                },
                "edges": {
                    "e1": {"source": "n1", "target": "n3", "source_output": 0, "target_input": 0},
                    "e2": {"source": "n2", "target": "n3", "source_output": 0, "target_input": 1},
                    "e3": {"source": "n3", "target": "n5", "source_output": 0, "target_input": 0},
                    "e4": {"source": "n4", "target": "n5", "source_output": 0, "target_input": 1}
                }
            }
        }
        file_path = temp_workflow_file(workflow)
        executor = WorkflowExecutor(str(file_path), modules=['math'])
        results = executor.execute()

        assert "n3" in results
        assert results["n3"] == 5.0  # 2 + 3
        assert "n5" in results
        assert results["n5"] == 10.0  # 5 * 2


class TestConstructorNodeExecution:
    """Test execution of constructor nodes."""

    def test_calculator_constructor(self, temp_workflow_file):
        """Test Calculator class instantiation."""
        workflow = {
            "workflow": {
                "nodes": {
                    "n1": {"node_type": "primitive", "type": "float", "value": 10.0},
                    "n2": {"node_type": "constructor", "type": "Calculator"}
                },
                "edges": {
                    "e1": {"source": "n1", "target": "n2", "source_output": 0, "target_input": 0}
                }
            }
        }
        file_path = temp_workflow_file(workflow)
        executor = WorkflowExecutor(str(file_path), modules=['math'])
        results = executor.execute()

        assert "n2" in results
        # Check it's a Calculator instance
        assert hasattr(results["n2"], 'value')
        assert results["n2"].value == 10.0


class TestMethodNodeExecution:
    """Test execution of method nodes."""

    def test_calculator_method(self, temp_workflow_file):
        """Test Calculator method execution."""
        workflow = {
            "workflow": {
                "nodes": {
                    "n1": {"node_type": "primitive", "type": "float", "value": 10.0},
                    "n2": {"node_type": "constructor", "type": "Calculator"},
                    "n3": {"node_type": "primitive", "type": "float", "value": 5.0},
                    "n4": {"type": "Calculator.add_to_value"}
                },
                "edges": {
                    "e1": {"source": "n1", "target": "n2", "source_output": 0, "target_input": 0},
                    "e2": {"source": "n2", "target": "n4", "source_output": -1, "target_input": 0},
                    "e3": {"source": "n3", "target": "n4", "source_output": 0, "target_input": 1}
                }
            }
        }
        file_path = temp_workflow_file(workflow)
        executor = WorkflowExecutor(str(file_path), modules=['math'])
        results = executor.execute()

        assert "n4" in results
        assert results["n4"] == 15.0  # 10 + 5


class TestTopologicalSorting:
    """Test topological sorting and execution order."""

    def test_simple_dag(self, temp_workflow_file):
        """Test topological sort on simple DAG."""
        workflow = {
            "workflow": {
                "nodes": {
                    "n1": {"node_type": "primitive", "type": "int", "value": 1},
                    "n2": {"node_type": "primitive", "type": "int", "value": 2},
                    "n3": {"type": "add"}
                },
                "edges": {
                    "e1": {"source": "n1", "target": "n3", "source_output": 0, "target_input": 0},
                    "e2": {"source": "n2", "target": "n3", "source_output": 0, "target_input": 1}
                }
            }
        }
        file_path = temp_workflow_file(workflow)
        executor = WorkflowExecutor(str(file_path), modules=['math'])
        execution_order = executor.get_execution_order()

        # n3 should come after n1 and n2
        n1_idx = execution_order.index("n1")
        n2_idx = execution_order.index("n2")
        n3_idx = execution_order.index("n3")

        assert n1_idx < n3_idx
        assert n2_idx < n3_idx

    def test_cycle_detection(self, circular_workflow_dict, temp_workflow_file):
        """Test that circular dependencies are detected."""
        file_path = temp_workflow_file(circular_workflow_dict)
        executor = WorkflowExecutor(str(file_path), modules=['math'])

        with pytest.raises(ValueError, match="Cycle detected"):
            executor.get_execution_order()


class TestEdgeOrdering:
    """Test that edge target_input ordering is respected."""

    def test_input_order_matters(self, temp_workflow_file):
        """Test that parameter order follows target_input values."""
        # math.pow(x, y) = x^y, so order matters
        workflow = {
            "workflow": {
                "nodes": {
                    "n1": {"node_type": "primitive", "type": "float", "value": 2.0},
                    "n2": {"node_type": "primitive", "type": "float", "value": 3.0},
                    "n3": {"type": "math.pow"}
                },
                "edges": {
                    "e1": {"source": "n1", "target": "n3", "source_output": 0, "target_input": 0},
                    "e2": {"source": "n2", "target": "n3", "source_output": 0, "target_input": 1}
                }
            }
        }
        file_path = temp_workflow_file(workflow)
        executor = WorkflowExecutor(str(file_path), modules=['math'])
        results = executor.execute()

        assert "n3" in results
        assert results["n3"] == 8.0  # 2^3 = 8, not 3^2 = 9