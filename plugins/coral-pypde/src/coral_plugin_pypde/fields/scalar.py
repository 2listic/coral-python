from typing import Any, Dict

from pde import ScalarField

from ..grids.base import PyPDEGridBase


class PyPDEScalarField:
    """Wrapper for a ScalarField of uniform random values — a simulation's initial condition."""

    def __init__(
        self, grid: PyPDEGridBase = PyPDEGridBase,
        vmin: float = 0.0,
        vmax: float = 0.0,
        field: Any = None,
    ):
        if isinstance(field, ScalarField):
            self.field = field
        else:
            self.field = ScalarField(grid.grid, len(grid.grid.shape))
        
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

    def plot(self, filename):
        if filename.endswith(".png"):
            print(self.field)
            self.field.plot(filename=filename)
        else:
            raise ValueError("coral-python only supports plots in png format atm.")
    
    def to_file(self, filename):
        if filename.endswith(".h5"):
            print(self.field)
            self.field.to_file(filename=filename)
        else:
            raise ValueError("coral-python only supports writing in the h5 format atm.")
