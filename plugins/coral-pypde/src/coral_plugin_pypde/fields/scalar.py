import ast
import numpy as np
from typing import Any, Dict
from pde import ScalarField

from ..grids.base import PyPDEGridBase


class PyPDEScalarField:
    """Wrapper for a ScalarField of uniform random values — a simulation's initial condition."""

    def __init__(
            self,
            grid: PyPDEGridBase = PyPDEGridBase,
            field_type: str = "",
            data: Any = None,
    ):
        
        if field_type=="random_uniform":
            assert type(data)==dict
            data = ast.literal_eval(data)
            self.field = ScalarField.random_uniform(grid.grid, **data)
        elif field_type=="array":
            assert type(data)==ScalarField
            self.field = data
        elif field_type=="field":
            assert type(data)==True
            self.field = data
        else:
            raise ValueError(f"invalid ``field_type`` selection, got {field_type}")

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
        "Wrapper for the ``plot`` method of a Scalarfield"
        if filename.endswith(".png"):
            print(self.field)
            self.field.plot(filename=filename)
        else:
            raise ValueError("coral-python only supports plots in png format atm.")
    
    def to_file(self, filename):
        "Wrapper for the ``to_file`` method of a Scalarfield"
        if filename.endswith(".h5"):
            print(self.field)
            self.field.to_file(filename=filename)
        else:
            raise ValueError("coral-python only supports writing in the h5 format atm.")
