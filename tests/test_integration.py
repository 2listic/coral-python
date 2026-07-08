"""
Integration tests for end-to-end workflow execution using real workflow files.
"""

import pytest
from executor import WorkflowExecutor
from pathlib import Path


class TestPhiFlowWorkflows:
    """Test PhiFlow physics simulation workflows."""

    @pytest.mark.phiflow
    @pytest.mark.integration
    def test_obstacle_workflow_execution(self, workflow_files):
        """Test obstacle workflow executes without errors."""
        try:
            executor = WorkflowExecutor(str(workflow_files["obstacle"]), modules=['phiflow'])
            results = executor.execute()

            # Verify workflow executed and produced results
            assert len(results) > 0
            assert isinstance(results, dict)

            # Verify no exceptions occurred
            print(f"Obstacle workflow executed successfully with {len(results)} nodes")

        except ImportError:
            pytest.skip("PhiFlow not available")

    @pytest.mark.phiflow
    @pytest.mark.integration
    def test_smoke_plume_workflow_execution(self, workflow_files):
        """Test smoke plume workflow executes without errors."""
        try:
            executor = WorkflowExecutor(str(workflow_files["smoke_plume"]), modules=['phiflow'])
            results = executor.execute()

            # Verify workflow executed and produced results
            assert len(results) > 0
            assert isinstance(results, dict)

            print(f"Smoke plume workflow executed successfully with {len(results)} nodes")

        except ImportError:
            pytest.skip("PhiFlow not available")
    
    @pytest.mark.phiflow
    @pytest.mark.integration
    def test_default_workflow_execution(self, workflow_files):
        """Test smoke plume workflow executes without errors."""
        try:
            executor = WorkflowExecutor(str(workflow_files["default"]), modules=['phiflow'])
            results = executor.execute()

            # Verify workflow executed and produced results
            assert len(results) > 0
            assert isinstance(results, dict)

            print(f"Default workflow executed successfully with {len(results)} nodes")

        except ImportError:
            pytest.skip("PhiFlow not available")


class TestMathWorkflows:
    """Test mathematical computation workflows."""

    @pytest.mark.math
    @pytest.mark.integration
    def test_math_workflow_execution(self, workflow_files):
        """Test math workflow executes and produces numeric results."""
        executor = WorkflowExecutor(str(workflow_files["math"]), modules=['math'])
        results = executor.execute()

        # Verify workflow executed
        assert len(results) > 0
        assert isinstance(results, dict)

        # Verify we have numeric results
        has_numeric = any(isinstance(v, (int, float)) for v in results.values())
        assert has_numeric, "Math workflow should produce numeric results"

        print(f"Math workflow executed successfully with {len(results)} nodes")

    @pytest.mark.math
    @pytest.mark.integration
    def test_classes_workflow_execution(self, workflow_files):
        """Test classes workflow (Calculator) executes correctly."""
        executor = WorkflowExecutor(str(workflow_files["classes"]), modules=['math'])
        results = executor.execute()

        # Verify workflow executed
        assert len(results) > 0
        assert isinstance(results, dict)

        # Check if any Calculator instances were created
        has_calculator = any(
            hasattr(v, 'value') and hasattr(v, 'add_to_value')
            for v in results.values()
        )

        print(f"Classes workflow executed successfully with {len(results)} nodes")
        if has_calculator:
            print("Calculator instance(s) created successfully")

    @pytest.mark.math
    @pytest.mark.integration
    def test_functions_workflow_execution(self, workflow_files):
        """Test functions workflow executes correctly."""
        executor = WorkflowExecutor(str(workflow_files["functions"]), modules=['math'])
        results = executor.execute()

        # Verify workflow executed
        assert len(results) > 0
        assert isinstance(results, dict)

        print(f"Functions workflow executed successfully with {len(results)} nodes")


class TestWorkflowValidation:
    """Test workflow validation and error handling."""

    @pytest.mark.integration
    def test_workflow_files_exist(self, workflow_files):
        """Test that all workflow files exist."""
        for name, path in workflow_files.items():
            assert path.exists(), f"Workflow file {name} not found at {path}"

    @pytest.mark.integration
    def test_workflow_files_valid_json(self, workflow_files):
        """Test that all workflow files contain valid JSON."""
        import json

        for name, path in workflow_files.items():
            with open(path, 'r') as f:
                try:
                    data = json.load(f)
                    assert isinstance(data, dict)
                    assert 'workflow' in data
                except json.JSONDecodeError as e:
                    pytest.fail(f"Workflow {name} has invalid JSON: {e}")

    @pytest.mark.integration
    def test_workflow_structure(self, workflow_files):
        """Test that workflows have required structure."""
        import json

        for name, path in workflow_files.items():
            with open(path, 'r') as f:
                data = json.load(f)

            workflow = data.get('workflow', {})
            assert 'nodes' in workflow, f"Workflow {name} missing 'nodes'"
            assert 'edges' in workflow, f"Workflow {name} missing 'edges'"
            assert isinstance(workflow['nodes'], dict), f"Workflow {name} nodes not a dict"
            assert isinstance(workflow['edges'], dict), f"Workflow {name} edges not a dict"


class TestModuleCompatibility:
    """Test that workflows work with their intended modules."""

    @pytest.mark.integration
    def test_phiflow_workflows_with_phiflow_module(self, workflow_files):
        """Test that PhiFlow workflows work with phiflow module."""
        phiflow_workflows = ["obstacle", "smoke_plume"]

        for workflow_name in phiflow_workflows:
            try:
                executor = WorkflowExecutor(
                    str(workflow_files[workflow_name]),
                    modules=['phiflow']
                )
                results = executor.execute()
                assert len(results) > 0
            except ImportError:
                pytest.skip(f"PhiFlow not available for {workflow_name}")

    @pytest.mark.integration
    def test_math_workflows_with_math_module(self, workflow_files):
        """Test that math workflows work with math module."""
        math_workflows = ["math", "classes", "functions"]

        for workflow_name in math_workflows:
            executor = WorkflowExecutor(
                str(workflow_files[workflow_name]),
                modules=['math']
            )
            results = executor.execute()
            assert len(results) > 0
            print(f"Workflow {workflow_name} executed with {len(results)} nodes")


class TestWorkflowResults:
    """Test workflow execution results."""

    @pytest.mark.math
    @pytest.mark.integration
    def test_math_workflow_produces_expected_types(self, workflow_files):
        """Test that math workflow produces expected result types."""
        executor = WorkflowExecutor(str(workflow_files["math"]), modules=['math'])
        results = executor.execute()

        # Check that results contain expected types
        result_types = {type(v).__name__ for v in results.values()}

        # Should have at least some numeric types
        numeric_types = {'int', 'float'}
        has_numeric = bool(numeric_types & result_types)
        assert has_numeric, f"Expected numeric types, got: {result_types}"

    @pytest.mark.math
    @pytest.mark.integration
    def test_classes_workflow_creates_instances(self, workflow_files):
        """Test that classes workflow creates class instances."""
        executor = WorkflowExecutor(str(workflow_files["classes"]), modules=['math'])
        results = executor.execute()

        # Check for object instances (not just primitives)
        has_objects = any(
            not isinstance(v, (int, float, str, bool, type(None)))
            for v in results.values()
        )

        assert has_objects, "Classes workflow should create object instances"


class TestErrorHandling:
    """Test error handling in workflow execution."""

    @pytest.mark.integration
    def test_missing_workflow_file(self):
        """Test that missing workflow file raises appropriate error."""
        with pytest.raises(FileNotFoundError):
            executor = WorkflowExecutor("nonexistent_workflow.json")

    @pytest.mark.integration
    def test_workflow_with_wrong_module(self, workflow_files):
        """Test that using wrong module may cause errors."""
        # Try to run a PhiFlow workflow with only math module
        # This should either skip missing functions or raise an error
        try:
            executor = WorkflowExecutor(
                str(workflow_files["obstacle"]),
                modules=['math']  # Wrong module for PhiFlow workflow
            )
            # Execution may fail due to missing functions
            results = executor.execute()
            # If it doesn't fail, at least check it ran
            assert isinstance(results, dict)
        except (KeyError, AttributeError, ValueError):
            # Expected - missing PhiFlow functions (ValueError: unknown node type for the module)
            pass
        except ImportError:
            pytest.skip("PhiFlow workflow file might not exist or have issues")


class TestExecutionPerformance:
    """Test workflow execution performance (non-critical)."""

    @pytest.mark.integration
    @pytest.mark.slow
    def test_math_workflow_execution_time(self, workflow_files):
        """Test that math workflow executes in reasonable time."""
        import time

        start = time.time()
        executor = WorkflowExecutor(str(workflow_files["math"]), modules=['math'])
        results = executor.execute()
        elapsed = time.time() - start

        assert len(results) > 0
        # Math workflow should complete quickly (< 5 seconds)
        assert elapsed < 5.0, f"Math workflow took {elapsed:.2f}s (expected < 5s)"
        print(f"Math workflow executed in {elapsed:.3f} seconds")


class TestWorkflowNodeCounts:
    """Test that workflows contain expected number of nodes."""

    @pytest.mark.integration
    def test_workflows_have_nodes(self, load_workflow):
        """Test that all workflows have at least one node."""
        workflow_names = ["obstacle", "smoke_plume", "math", "classes", "functions"]

        for name in workflow_names:
            workflow = load_workflow(name)
            nodes = workflow['workflow']['nodes']
            assert len(nodes) > 0, f"Workflow {name} has no nodes"
            print(f"Workflow {name} has {len(nodes)} nodes")

    @pytest.mark.integration
    def test_workflows_have_edges(self, load_workflow):
        """Test that most workflows have edges (connections)."""
        workflow_names = ["obstacle", "smoke_plume", "math", "classes", "functions"]

        for name in workflow_names:
            workflow = load_workflow(name)
            edges = workflow['workflow']['edges']
            # Most workflows should have edges (some single-node workflows may not)
            if len(workflow['workflow']['nodes']) > 1:
                assert len(edges) > 0, f"Multi-node workflow {name} has no edges"


class TestDeterministicExecution:
    """Test that workflow execution is deterministic."""

    @pytest.mark.math
    @pytest.mark.integration
    def test_math_workflow_deterministic(self, workflow_files):
        """Test that math workflow produces same results on multiple runs."""
        results1 = WorkflowExecutor(
            str(workflow_files["math"]),
            modules=['math']
        ).execute()

        results2 = WorkflowExecutor(
            str(workflow_files["math"]),
            modules=['math']
        ).execute()

        # Results should be identical
        assert results1.keys() == results2.keys()

        # Compare values (for numeric types)
        for key in results1.keys():
            val1, val2 = results1[key], results2[key]
            if isinstance(val1, (int, float)):
                assert val1 == val2, f"Node {key} produced different results: {val1} vs {val2}"