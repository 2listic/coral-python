from typing import Any, Dict

from pde import ScalarField

from ..grids.cartesian import PyPDEUnitGrid

class PyPDEScalarField:
    """Wrapper for a ScalarField of uniform random values — a simulation's initial condition."""

    def __init__(self, grid: PyPDEUnitGrid, vmin: float, vmax: float):
        self.field = ScalarField.random_uniform(grid.grid, vmin, vmax)

    @classmethod
    def _holding(cls, field: Any) -> "PyPDEScalarField":
        """Wrap a field py-pde produced, skipping the random initial condition.

        The public constructor *is* the initial-condition node, so it cannot double as a way to
        carry a solved field back out of ``PyPDEDiffusionPDE.solve``. Underscored so the registry
        never offers it as a node: only public methods become ``Class.method`` entries.
        """
        wrapper = cls.__new__(cls)
        wrapper.field = field
        return wrapper
