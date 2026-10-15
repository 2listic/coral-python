from ast import literal_eval

from pde import CartesianGrid, UnitGrid

from .base import PyPDEGridBase


class PyPDEUnitGrid(PyPDEGridBase):
    """Wrapper for a two-dimensional UnitGrid.
    The parent class does nothing, but serves as a common feature with the other grids.

    py-pde takes the shape as a sequence; two scalar ports are what a graph can wire.
    """

    def __init__(self, x: int, y: int):
        self.grid = UnitGrid([x, y])


class PyPDECartesianGrid(PyPDEGridBase):
    """Wrapper for a 1- or 2-dimensional CartesianGrid.
    The parent class does nothing, but serves as a common feature with the other grids.

    py-pde takes the shape as a sequence; two scalar ports are what a graph can wire.
    """

    def __init__(self, bounds: str, shape: str):
        bc = literal_eval(bounds)
        sh = literal_eval(shape)
        self.grid = CartesianGrid(bc, sh)
