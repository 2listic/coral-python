"""The one test in this repo that runs a fluid simulation.

Marked ``slow``, and deliberately singular. Four phiflow graphs are shipped and all four are checked
for validity in ``test_graphs_validate.py`` at no cost; executing them was previously done four times
over, for 58.75 seconds of a 59.35-second suite, in exchange for four ``isinstance(results, dict)``
assertions. Those are gone.

What only a real run can cover is what stays here: ``phiflow_iterate``'s body after the unwrapping —
``jit_compile``, ``fluid.make_incompressible``, ``iterate`` — and ``phiflow_plot_and_save``'s render to
a file. Everything *around* those (the wrapper constructors, the unwrap dispatch, the union guard) is
covered in milliseconds by ``tests/unit/``.

One graph is enough because the graphs differ in their wiring, not in the code they reach: they all end
in the same iterate-then-plot pair. The wiring is what ``test_graphs_validate.py`` checks, for all four.
"""

import pytest
from coral_app.executor import WorkflowExecutor
from phiflow_suite import EXAMPLES, PLUGIN_NAME

#: The example a user is told to run: `coral -p "phiflow" run examples/phiflow/network-from-fe.json`.
EXAMPLE = EXAMPLES / "phiflow" / "network-from-fe.json"

#: What its `phiflow_plot_and_save` node is wired to write.
OUTPUT_FILE = "simulation.mp4"


@pytest.mark.slow
class TestTheShippedExampleRuns:
    """Execute the documented example end to end, once."""

    @pytest.fixture(scope="class")
    def executed(self, tmp_path_factory):
        """Run the example in a throwaway directory, returning the executor and that directory.

        Class-scoped: this is the expensive fixture in the repo, so the assertions below share one run
        rather than paying for it each. The directory is created here rather than taken from the
        autouse ``isolate_cwd`` fixture, which is function-scoped.
        """
        import os

        directory = tmp_path_factory.mktemp("phiflow-example")
        previous = os.getcwd()
        os.chdir(directory)
        try:
            executor = WorkflowExecutor(str(EXAMPLE), plugins=[PLUGIN_NAME])
            executor.execute()
        finally:
            os.chdir(previous)
        return executor, directory

    def test_every_node_produced_a_result(self, executed):
        """GIVEN the shipped example
        WHEN it is executed
        THEN every node it declares has a result.

        One result per node, rather than "did not raise": the executor only visits what the graph's
        order contains, so a node left unreachable would otherwise pass unnoticed."""
        executor, _ = executed

        assert set(executor.results) == set(executor.graph.nodes)

    def test_the_simulation_returned_three_trajectories(self, executed):
        """GIVEN `phiflow_iterate` in the example
        WHEN the graph has run
        THEN its result is the three-element tuple its annotation promises.

        This is the shape the registry advertises as three output ports, and the reason a downstream
        edge can select the smoke trajectory with `source_output`. Its annotation is `Tuple[Any, Any,
        Any]`, so nothing before execution can verify it — which is exactly why it is asserted here."""
        executor, _ = executed

        iterate_nodes = [
            node_id
            for node_id, node in executor.graph.nodes.items()
            if node["type"] == "phiflow_iterate"
        ]
        assert iterate_nodes, "the example no longer contains a phiflow_iterate node"

        for node_id in iterate_nodes:
            result = executor.results[node_id]
            assert isinstance(result, tuple)
            assert len(result) == 3

    def test_the_animation_was_written(self, executed):
        """GIVEN `phiflow_plot_and_save` wired to a filename
        WHEN the graph has run
        THEN the file exists and is not empty, in the directory the run happened in.

        The render is the other half of what only a real run reaches, and a file that exists but is
        empty is the failure mode a mere "did not raise" would miss."""
        _, directory = executed

        output = directory / OUTPUT_FILE

        assert output.exists(), f"{OUTPUT_FILE} was not written into {directory}"
        assert output.stat().st_size > 0
