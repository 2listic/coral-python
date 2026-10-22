"""The tests in this package that execute a shipped graph end to end.

Two of them run a simulation and are marked ``slow``: the diffusion example solves on a 32x32 grid
to t=20 and renders twenty frames to an mp4, about twelve seconds; the obstacles example integrates
on a 120x120 grid to t=100, about eight. The Poisson example is one linear solve on 32 cells, with
no time stepping, so it runs in the fast lane. Every graph is *validated* for free in
``test_graphs_validate.py``, so what stays here is only what a real run can reach — that the
wrappers actually drive py-pde, that each sink receives data, and that each movie is closed so its
file is complete.
"""

import os
from ast import literal_eval

import numpy
import pytest
from coral_app.executor import WorkflowExecutor
from coral_plugin_pypde import PyPDEScalarField
from pde import solve_poisson_equation
from pypde_suite import EXAMPLES, PLUGIN_NAME, node_named

#: The example a user is told to run: `coral -p "pypde" run examples/pypde/diffusion.json`.
EXAMPLE = EXAMPLES / "pypde" / "diffusion.json"

#: What the graph's two sinks are wired to write, relative to the working directory.
OUTPUT_FILES = ("diffusion.hdf5", "diffusion.mp4")

POISSON = EXAMPLES / "pypde" / "poisson.json"
POISSON_OUTPUT_FILES = ("poisson.h5", "poisson.png")

OBSTACLES = EXAMPLES / "pypde" / "obstacles.json"
OBSTACLES_OUTPUT_FILES = ("obstacles.hdf5", "obstacles.mp4")


def solved(executor):
    """The field the ``solve`` node returned. A solve modifies its equation and both trackers, so
    it passes them on too: its outputs are the equation, the field, the storage and the plot."""
    return executor.results[node_named(executor.graph, "solve")][1]


def _execute(graph, directory):
    """Run ``graph`` from ``directory``, returning the executor and that directory.

    Each class below calls it from a class-scoped fixture: the run is the expensive part, so a
    class's assertions share one rather than paying for it each. The directory comes from
    ``tmp_path_factory`` rather than the autouse ``isolate_cwd`` fixture, which is function-scoped.
    """
    previous = os.getcwd()
    os.chdir(directory)
    try:
        executor = WorkflowExecutor(str(graph), plugins=[PLUGIN_NAME])
        executor.execute()
    finally:
        os.chdir(previous)
    return executor, directory


@pytest.mark.slow
class TestTheShippedExampleRuns:
    """Execute the documented example end to end, once."""

    @pytest.fixture(scope="class")
    def executed(self, tmp_path_factory):
        """The diffusion example, run once in a throwaway directory."""
        return _execute(EXAMPLE, tmp_path_factory.mktemp("pypde-example"))

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

        final = solved(executor)
        initial = executor.results[node_named(executor.graph, "initial_state")]

        assert isinstance(final, PyPDEScalarField)
        assert final is not initial

    def test_the_field_actually_evolved(self, executed):
        """GIVEN the initial condition and the final state
        WHEN their data are compared
        THEN they differ — the solver did work, rather than handing back what it was given."""
        executor, _ = executed

        final = solved(executor)
        initial = executor.results[node_named(executor.graph, "initial_state")]

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


class TestThePoissonExampleRuns:
    """Execute the Poisson example end to end — cheap enough for the fast lane."""

    @pytest.fixture(scope="class")
    def executed(self, tmp_path_factory):
        """The Poisson example, run once in a throwaway directory."""
        return _execute(POISSON, tmp_path_factory.mktemp("pypde-poisson"))

    def test_every_node_produced_a_result(self, executed):
        """GIVEN the Poisson example
        WHEN it is executed
        THEN every node it declares has a result."""
        executor, _ = executed

        assert set(executor.results) == set(executor.graph.nodes)

    def test_the_solution_is_py_pde_s_own(self, executed):
        """GIVEN the graph's source term and boundary
        WHEN the graph has run
        THEN the solve node holds a PyPDEScalarField equal to what py-pde computes directly from
        those same two inputs."""
        executor, _ = executed
        source_term = executor.results[node_named(executor.graph, "source_term")]
        boundary = executor.results[node_named(executor.graph, "boundary")]

        result = executor.results[node_named(executor.graph, "solve")]

        expected = solve_poisson_equation(source_term.field, bc=literal_eval(boundary))
        assert isinstance(result, PyPDEScalarField)
        numpy.testing.assert_allclose(result.field.data, expected.data)

    @pytest.mark.parametrize("filename", POISSON_OUTPUT_FILES)
    def test_each_output_was_written(self, executed, filename):
        """GIVEN the ``to_file`` and ``plot`` nodes wired to filenames
        WHEN the graph has run
        THEN each file exists and is not empty, in the directory the run happened in."""
        _, directory = executed

        output = directory / filename

        assert output.exists(), f"{filename} was not written into {directory}"
        assert output.stat().st_size > 0


@pytest.mark.slow
class TestTheObstaclesExampleRuns:
    """Execute the obstacles example end to end, once."""

    @pytest.fixture(scope="class")
    def executed(self, tmp_path_factory):
        """The obstacles example, run once in a throwaway directory."""
        return _execute(OBSTACLES, tmp_path_factory.mktemp("pypde-obstacles"))

    def test_every_node_produced_a_result(self, executed):
        """GIVEN the obstacles example
        WHEN it is executed
        THEN every node it declares has a result."""
        executor, _ = executed

        assert set(executor.results) == set(executor.graph.nodes)

    def test_the_solver_returned_a_wrapped_field_that_evolved(self, executed):
        """GIVEN the initial condition and the solve node
        WHEN the graph has run
        THEN the result is a PyPDEScalarField, not the one it was handed, and its data differ."""
        executor, _ = executed

        final = solved(executor)
        initial = executor.results[node_named(executor.graph, "initial_state")]

        assert isinstance(final, PyPDEScalarField)
        assert final is not initial
        assert not numpy.array_equal(final.field.data, initial.field.data)

    def test_the_fixed_regions_kept_their_values(self, executed):
        """GIVEN the source, absorber and obstacle masks the equation was built from
        WHEN the graph has run
        THEN the source is still 1, and the absorber and the obstacle are still 0.

        This is what the obstacle equation adds to plain diffusion: its rate is zero on those
        cells, so they hold the values the initial condition gave them however long it runs."""
        executor, _ = executed
        equation = executor.results[node_named(executor.graph, "pde")].equation

        final = solved(executor).field.data

        assert numpy.all(final[equation.source] == 1.0)
        assert numpy.all(final[equation.absorber] == 0.0)
        assert numpy.all(final[equation.obstacle] == 0.0)

    @pytest.mark.parametrize("filename", OBSTACLES_OUTPUT_FILES)
    def test_each_output_was_written(self, executed, filename):
        """GIVEN the storage and movie nodes wired to filenames
        WHEN the graph has run
        THEN each file exists and is not empty, in the directory the run happened in."""
        _, directory = executed

        output = directory / filename

        assert output.exists(), f"{filename} was not written into {directory}"
        assert output.stat().st_size > 0
