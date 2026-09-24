"""The one test in this package that runs a simulation.

Marked ``slow``: it solves the diffusion equation on a 32x32 grid to t=20 and renders twenty frames
to an mp4, about twelve seconds. The graph is *validated* for free in ``test_graphs_validate.py``,
so what stays here is only what a real run can reach — that the wrappers actually drive py-pde, that
both trackers receive data, and that the movie is closed so its file is complete.
"""

import os

import numpy
import pytest
from coral_app.executor import WorkflowExecutor
from coral_plugin_pypde import PyPDEScalarField
from pypde_suite import EXAMPLES, PLUGIN_NAME

#: The example a user is told to run: `coral -p "pypde" run examples/pypde/diffusion.json`.
EXAMPLE = EXAMPLES / "pypde" / "diffusion.json"

#: What the graph's two sinks are wired to write, relative to the working directory.
OUTPUT_FILES = ("diffusion.hdf5", "diffusion.mp4")

#: The graph's node ids for the initial condition and the solver — the JSON has no field for a
#: name, so the two the assertions need are pinned here beside them.
NODES = {"initial_state": "5", "solve": "20"}


@pytest.mark.slow
class TestTheShippedExampleRuns:
    """Execute the documented example end to end, once."""

    @pytest.fixture(scope="class")
    def executed(self, tmp_path_factory):
        """Run the example in a throwaway directory, returning the executor and that directory.

        Class-scoped: the run is the expensive part, so the assertions below share one rather than
        paying for it each. The directory is created here rather than taken from the autouse
        ``isolate_cwd`` fixture, which is function-scoped.
        """
        directory = tmp_path_factory.mktemp("pypde-example")
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

    def test_the_solver_returned_a_wrapped_field(self, executed):
        """GIVEN the solve node
        WHEN the graph has run
        THEN its result is a PyPDEScalarField, and not the wrapper it was handed.

        Both halves matter. The type is what makes the output wirable into a further node at all;
        that it is a *different* object is what shows ``_holding`` carried py-pde's result out,
        rather than the input state being mutated and passed back."""
        executor, _ = executed

        final = executor.results[NODES["solve"]]
        initial = executor.results[NODES["initial_state"]]

        assert isinstance(final, PyPDEScalarField)
        assert final is not initial

    def test_the_field_actually_evolved(self, executed):
        """GIVEN the initial condition and the final state
        WHEN their data are compared
        THEN they differ — the solver did work, rather than handing back what it was given."""
        executor, _ = executed

        final = executor.results[NODES["solve"]]
        initial = executor.results[NODES["initial_state"]]

        assert not numpy.array_equal(final.field.data, initial.field.data)

    @pytest.mark.parametrize("filename", OUTPUT_FILES)
    def test_each_output_was_written(self, executed, filename):
        """GIVEN the storage and movie nodes wired to filenames
        WHEN the graph has run
        THEN each file exists and is not empty, in the directory the run happened in.

        The mp4 is the half that only a complete run produces: the movie holds its file open until
        ``solve`` saves it, so a wrapper that forgot that call would leave an empty file here."""
        _, directory = executed

        output = directory / filename

        assert output.exists(), f"{filename} was not written into {directory}"
        assert output.stat().st_size > 0
