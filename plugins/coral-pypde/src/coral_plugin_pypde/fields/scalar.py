from ast import literal_eval
from typing import Any

from pde import ScalarField

from ..grids.base import PyPDEGridBase


class PyPDEScalarField:
    """Wrapper for a ScalarField — a simulation's initial condition.

    ``field_type`` picks how ``data`` is read: ``"random_uniform"`` takes the keyword arguments
    of ``ScalarField.random_uniform`` as a dict literal (``'{"vmin": 0.2, "vmax": 0.3}'``);
    ``"expression"`` takes a formula in the grid's coordinates (``"1"``, ``"sin(2*pi*x)"``).
    """

    def __init__(
        self,
        grid: PyPDEGridBase,
        field_type: str,
        data: str,
    ):
        if field_type == "random_uniform":
            data = literal_eval(data)
            self.field = ScalarField.random_uniform(grid.grid, **data)
        elif field_type == "expression":
            self.field = ScalarField.from_expression(grid.grid, data)
        else:
            raise ValueError(f"invalid ``field_type`` selection, got {field_type}")

    @classmethod
    def _holding(cls, field: Any) -> "PyPDEScalarField":
        """Wrap a field py-pde produced, skipping the random initial condition.

        The public constructor *is* the initial-condition node, so it cannot double as a way to
        carry a solved field back out of ``PyPDEDiffusionPDE.solve``. Not declared as a method, so
        the registry never offers it as a node.
        """
        wrapper = cls.__new__(cls)
        wrapper.field = field
        return wrapper

    def plot(self, filename: str) -> None:
        "Wrapper for the ``plot`` method of a Scalarfield"
        if filename.endswith(".png"):
            print(self.field)
            self.field.plot(filename=filename)
        else:
            raise ValueError("coral-python only supports plots in png format atm.")

    def to_file(self, filename: str) -> None:
        "Wrapper for the ``to_file`` method of a Scalarfield"
        if filename.endswith(".h5"):
            print(self.field)
            self.field.to_file(filename=filename)
        else:
            raise ValueError("coral-python only supports writing in the h5 format atm.")
