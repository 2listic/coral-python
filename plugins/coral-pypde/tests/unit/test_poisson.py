"""The Poisson solver node, called directly.

It solves an equation, unlike the constructors in ``test_wrappers.py``, but it is not a simulation:
one linear solve on 32 cells, no time stepping. So it runs in the fast lane.
"""

import numpy
from coral_plugin_pypde import PyPDECartesianGrid, PyPDEScalarField, pypde_solve_poisson_equation
from pde import ScalarField, solve_poisson_equation


class TestSolvePoissonEquation:
    """A boundary written as a dict literal, the solution handed back as a typed field."""

    def test_it_returns_py_pde_s_own_solution_wrapped(self):
        """GIVEN a constant source term on a 1-D grid and a boundary written as a dict literal
        WHEN pypde_solve_poisson_equation is called
        THEN it returns a PyPDEScalarField holding the solution py-pde computes for the same
        problem, and not the field it was handed."""
        grid = PyPDECartesianGrid("[[0.0, 1.0]]", "32")
        source = PyPDEScalarField(grid, "expression", "1")

        result = pypde_solve_poisson_equation(
            source, '{"x-": {"value": 0}, "x+": {"derivative": 1}}'
        )

        expected = solve_poisson_equation(
            ScalarField(grid.grid, 1), bc={"x-": {"value": 0}, "x+": {"derivative": 1}}
        )
        assert isinstance(result, PyPDEScalarField)
        assert result is not source
        numpy.testing.assert_allclose(result.field.data, expected.data)
