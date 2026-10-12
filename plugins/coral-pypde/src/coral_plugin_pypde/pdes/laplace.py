import ast
from typing import Any, Dict

from pde import solve_poisson_equation, solve_laplace_equation

from ..fields.scalar import PyPDEScalarField


def pypde_solve_poisson_equation(
    field: PyPDEScalarField,
    boundary: str,
) -> Any:
    """Solve Poisson equation using pypde `solve_poisson_equation`"""
    boundary = ast.literal_eval(boundary)
    result = solve_poisson_equation(field.field, bc=boundary)
    
    return PyPDEScalarField(field=result)


def pypde_solve_laplace_equation():
    """Solve Laplace equation using pypde `solve_poisson_equation`"""
    pass
