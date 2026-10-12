"""
Solving Poisson's equation in 1d
================================

This example shows how to solve a 1d Poisson equation with boundary conditions.

Adapted from `poisson_eq_1D.py` at:
https://github.com/zwicker-group/py-pde/blob/master/examples/simple_pdes/poisson_eq_1d.py
"""

from pde import CartesianGrid, ScalarField, solve_poisson_equation

grid = CartesianGrid([[0, 1]], 32, periodic=False)
field = ScalarField(grid, 1)
result = solve_poisson_equation(field, bc={"x-": {"value": 0}, "x+": {"derivative": 1}})

result.plot(filename='poisson_1D.png')
result.to_file(filename='poisson_1D.h5')
