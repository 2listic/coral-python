"""
Integration tests for end-to-end workflow execution using real workflow files.
"""

import pytest
from coral_app.executor import WorkflowExecutor


class TestPhiFlowWorkflows:
    """Test PhiFlow physics simulation workflows."""

    @pytest.mark.phiflow
    @pytest.mark.integration
    def test_obstacle_workflow_execution(self, workflow_files):
        """Test obstacle workflow executes without errors."""
        try:
            executor = WorkflowExecutor(str(workflow_files["obstacle"]), plugins=["phiflow"])
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
            executor = WorkflowExecutor(str(workflow_files["smoke_plume"]), plugins=["phiflow"])
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
            executor = WorkflowExecutor(str(workflow_files["default"]), plugins=["phiflow"])
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
        executor = WorkflowExecutor(str(workflow_files["math"]), plugins=["math"])
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
        executor = WorkflowExecutor(str(workflow_files["classes"]), plugins=["math"])
        results = executor.execute()

        # Verify workflow executed
        assert len(results) > 0
        assert isinstance(results, dict)

        # Check if any Calculator instances were created
        has_calculator = any(
            hasattr(v, "value") and hasattr(v, "add_to_value") for v in results.values()
        )

        print(f"Classes workflow executed successfully with {len(results)} nodes")
        if has_calculator:
            print("Calculator instance(s) created successfully")

    @pytest.mark.math
    @pytest.mark.integration
    def test_functions_workflow_execution(self, workflow_files):
        """Test functions workflow executes correctly."""
        executor = WorkflowExecutor(str(workflow_files["functions"]), plugins=["math"])
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
            with open(path, "r") as f:
                try:
                    data = json.load(f)
                    assert isinstance(data, dict)
                    assert "workflow" in data
                except json.JSONDecodeError as e:
                    pytest.fail(f"Workflow {name} has invalid JSON: {e}")

    @pytest.mark.integration
    def test_workflow_structure(self, workflow_files):
        """Test that workflows have required structure."""
        import json

        for name, path in workflow_files.items():
            with open(path, "r") as f:
                data = json.load(f)

            workflow = data.get("workflow", {})
            assert "nodes" in workflow, f"Workflow {name} missing 'nodes'"
            assert "edges" in workflow, f"Workflow {name} missing 'edges'"
            assert isinstance(workflow["nodes"], dict), f"Workflow {name} nodes not a dict"
            assert isinstance(workflow["edges"], dict), f"Workflow {name} edges not a dict"


class TestPluginCompatibility:
    """Test that workflows work with their intended plugins."""

    @pytest.mark.phiflow
    @pytest.mark.integration
    def test_phiflow_workflows_with_phiflow_plugin(self, workflow_files):
        """Test that PhiFlow workflows work with the phiflow plugin."""
        phiflow_workflows = ["obstacle", "smoke_plume"]

        for workflow_name in phiflow_workflows:
            try:
                executor = WorkflowExecutor(str(workflow_files[workflow_name]), plugins=["phiflow"])
                results = executor.execute()
                assert len(results) > 0
            except ImportError:
                pytest.skip(f"PhiFlow not available for {workflow_name}")

    @pytest.mark.math
    @pytest.mark.integration
    def test_math_workflows_with_math_plugin(self, workflow_files):
        """Test that math workflows work with the math plugin."""
        math_workflows = ["math", "classes", "functions"]

        for workflow_name in math_workflows:
            executor = WorkflowExecutor(str(workflow_files[workflow_name]), plugins=["math"])
            results = executor.execute()
            assert len(results) > 0
            print(f"Workflow {workflow_name} executed with {len(results)} nodes")


class TestWorkflowResults:
    """Test workflow execution results."""

    @pytest.mark.math
    @pytest.mark.integration
    def test_math_workflow_produces_expected_types(self, workflow_files):
        """Test that math workflow produces expected result types."""
        executor = WorkflowExecutor(str(workflow_files["math"]), plugins=["math"])
        results = executor.execute()

        # Check that results contain expected types
        result_types = {type(v).__name__ for v in results.values()}

        # Should have at least some numeric types
        numeric_types = {"int", "float"}
        has_numeric = bool(numeric_types & result_types)
        assert has_numeric, f"Expected numeric types, got: {result_types}"

    @pytest.mark.math
    @pytest.mark.integration
    def test_classes_workflow_creates_instances(self, workflow_files):
        """Test that classes workflow creates class instances."""
        executor = WorkflowExecutor(str(workflow_files["classes"]), plugins=["math"])
        results = executor.execute()

        # Check for object instances (not just primitives)
        has_objects = any(
            not isinstance(v, (int, float, str, bool, type(None))) for v in results.values()
        )

        assert has_objects, "Classes workflow should create object instances"


class TestErrorHandling:
    """Test error handling in workflow execution."""

    @pytest.mark.integration
    def test_missing_workflow_file(self):
        """Test that missing workflow file raises appropriate error."""
        with pytest.raises(FileNotFoundError):
            WorkflowExecutor("nonexistent_workflow.json")

    @pytest.mark.math
    @pytest.mark.integration
    def test_workflow_with_wrong_plugin(self, workflow_files):
        """Test that using the wrong plugin may cause errors."""
        # Try to run a PhiFlow workflow with only the math plugin
        # This should either skip missing functions or raise an error
        try:
            executor = WorkflowExecutor(
                str(workflow_files["obstacle"]),
                plugins=["math"],  # Wrong plugin for PhiFlow workflow
            )
            # Execution may fail due to missing functions
            results = executor.execute()
            # If it doesn't fail, at least check it ran
            assert isinstance(results, dict)
        except (KeyError, AttributeError, ValueError):
            # Expected - missing PhiFlow functions (ValueError: unknown node type for the plugin)
            pass
        except ImportError:
            pytest.skip("PhiFlow workflow file might not exist or have issues")


class TestExecutionPerformance:
    """Test workflow execution performance (non-critical)."""

    @pytest.mark.math
    @pytest.mark.integration
    @pytest.mark.slow
    def test_math_workflow_execution_time(self, workflow_files):
        """Test that math workflow executes in reasonable time."""
        import time

        start = time.time()
        executor = WorkflowExecutor(str(workflow_files["math"]), plugins=["math"])
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
            nodes = workflow["workflow"]["nodes"]
            assert len(nodes) > 0, f"Workflow {name} has no nodes"
            print(f"Workflow {name} has {len(nodes)} nodes")

    @pytest.mark.integration
    def test_workflows_have_edges(self, load_workflow):
        """Test that most workflows have edges (connections)."""
        workflow_names = ["obstacle", "smoke_plume", "math", "classes", "functions"]

        for name in workflow_names:
            workflow = load_workflow(name)
            edges = workflow["workflow"]["edges"]
            # Most workflows should have edges (some single-node workflows may not)
            if len(workflow["workflow"]["nodes"]) > 1:
                assert len(edges) > 0, f"Multi-node workflow {name} has no edges"


class TestDeterministicExecution:
    """Test that workflow execution is deterministic."""

    @pytest.mark.math
    @pytest.mark.integration
    def test_math_workflow_deterministic(self, workflow_files):
        """Test that math workflow produces same results on multiple runs."""
        results1 = WorkflowExecutor(str(workflow_files["math"]), plugins=["math"]).execute()

        results2 = WorkflowExecutor(str(workflow_files["math"]), plugins=["math"]).execute()

        # Results should be identical
        assert results1.keys() == results2.keys()

        # Compare values (for numeric types)
        for key in results1.keys():
            val1, val2 = results1[key], results2[key]
            if isinstance(val1, (int, float)):
                assert val1 == val2, f"Node {key} produced different results: {val1} vs {val2}"


# Node ids in the four `network-collections-*` fixtures, by the name each node plays in its graph.
#
# The graphs key their nodes by decimal integer, as the protocol requires (the editor's exporter
# `parseInt`s every endpoint and the reference C++ backend `std::stoi`s every key), which leaves the
# ids carrying no meaning. These maps are where the meaning lives, so an assertion below still reads
# as a sentence about the graph rather than about node "8". Every node is listed, not only the
# asserted ones, so the map doubles as the graph's legend.
#
# Nothing ties a map to its file: renumber a fixture without updating the map here and the
# assertions move to the wrong nodes. Both are hand-maintained together, deliberately — the
# alternative was a `"name"` field the protocol has no room for.
LIST_NODES = {
    "one": "0",
    "two": "1",
    "three": "2",
    "index_0": "3",
    "index_1": "4",
    "empty": "5",
    "with_one": "6",
    "with_two": "7",
    "with_three": "8",
    "size": "9",
    "second": "10",
    "without_first": "11",
}

SET_NODES = {
    "five": "0",
    "seven": "1",
    "five_again": "2",
    "index_0": "3",
    "empty": "4",
    "with_five": "5",
    "with_seven": "6",
    "with_duplicate": "7",
    "size": "8",
    "as_list": "9",
    "smallest": "10",
}

DICT_NODES = {
    "key_alpha": "0",
    "key_beta": "1",
    "value_alpha": "2",
    "value_beta": "3",
    "empty": "4",
    "with_alpha": "5",
    "with_both": "6",
    "beta_value": "7",
    "without_alpha": "8",
    "size": "9",
}

MATH_NODES = {
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


class TestCollectionWorkflows:
    """End-to-end graphs built from the host's builtin collection nodes.

    Unlike every other class here, the first three assert **result values**, not just that execution
    finished — a collection graph whose answer is wrong is exactly the failure worth catching.

    They also pass ``plugins=[]``, which is the point: these node types need no plugin. That
    contract cannot be expressed through the CLI (an empty ``-p`` means *all* installed
    plugins), so it is asserted here or nowhere. None of them carries a plugin marker; only the
    interop graph, which reaches into ``math``, does.

    Results are keyed by node id, so each assertion goes through the graph's name map above.
    """

    @pytest.mark.integration
    def test_list_workflow_values(self, workflow_files):
        """GIVEN a graph appending 1, 2, 3 to a new list, then measuring and indexing it
        WHEN it runs with no plugin at all
        THEN the size is 3, index 1 holds 2, and removal drops index 0."""
        results = WorkflowExecutor(str(workflow_files["collections_list"]), plugins=[]).execute()

        assert results[LIST_NODES["empty"]] == []
        assert results[LIST_NODES["with_three"]] == [1, 2, 3]
        assert results[LIST_NODES["size"]] == 3
        assert results[LIST_NODES["second"]] == 2
        assert results[LIST_NODES["without_first"]] == [2, 3]

    @pytest.mark.integration
    def test_list_append_leaves_its_input_untouched(self, workflow_files):
        """GIVEN a chain of list_append nodes, each feeding the next
        WHEN the graph has run
        THEN every intermediate list is still its own value in ``results`` — purity holding end to
        end, not just in the unit tests, which is what lets two consumers read one node."""
        results = WorkflowExecutor(str(workflow_files["collections_list"]), plugins=[]).execute()

        assert results[LIST_NODES["empty"]] == []
        assert results[LIST_NODES["with_one"]] == [1]
        assert results[LIST_NODES["with_two"]] == [1, 2]
        # `with_three` was fed to list_size, list_get *and* list_remove_at; none of them touched it.
        assert results[LIST_NODES["with_three"]] == [1, 2, 3]

    @pytest.mark.integration
    def test_dict_workflow_values(self, workflow_files):
        """GIVEN a graph setting two keys, reading one, then deleting the other
        WHEN it runs with no plugin at all
        THEN the read returns its value, the delete leaves one entry, and the source dict is intact."""
        results = WorkflowExecutor(str(workflow_files["collections_dict"]), plugins=[]).execute()

        assert results[DICT_NODES["with_both"]] == {"alpha": 1.5, "beta": 2.5}
        assert results[DICT_NODES["beta_value"]] == 2.5
        assert results[DICT_NODES["without_alpha"]] == {"beta": 2.5}
        assert results[DICT_NODES["size"]] == 1

    @pytest.mark.integration
    def test_set_workflow_deduplicates(self, workflow_files):
        """GIVEN a graph adding 5, 7 and 5 again to a new set
        WHEN it runs with no plugin at all
        THEN the size is 2 rather than 3 — deduplication observed through the graph — and
        set_to_list yields a sorted list the next node can index."""
        results = WorkflowExecutor(str(workflow_files["collections_set"]), plugins=[]).execute()

        assert results[SET_NODES["with_duplicate"]] == {5, 7}
        assert results[SET_NODES["size"]] == 2
        assert results[SET_NODES["as_list"]] == [5, 7]
        assert results[SET_NODES["smallest"]] == 5

    @pytest.mark.math
    @pytest.mark.integration
    def test_collection_feeds_a_plugin_function(self, workflow_files):
        """GIVEN two floats stored in a list, read back and summed by the math plugin's ``add``
        WHEN the graph runs with the math plugin
        THEN the sum is 7.0.

        This is the interop case decision 2 was taken for: because a builtin returns a real ``list``
        holding real floats, a plugin function consumes them with no conversion node in between.
        """
        results = WorkflowExecutor(
            str(workflow_files["collections_math"]), plugins=["math"]
        ).execute()

        assert results[MATH_NODES["with_both"]] == [3.0, 4.0]
        assert results[MATH_NODES["total"]] == 7.0
