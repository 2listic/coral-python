from ast import literal_eval

from pde import solve_poisson_equation

from ..fields.scalar import PyPDEScalarField


def pypde_solve_poisson_equation(
    field: PyPDEScalarField,
    boundary: str,
) -> PyPDEScalarField:
    """Solve Poisson equation using pypde `solve_poisson_equation`"""
    boundary = literal_eval(boundary)
    result = solve_poisson_equation(field.field, bc=boundary)

    return PyPDEScalarField._holding(result)


# TODO: wrap py-pde's `solve_laplace_equation` as a node.
