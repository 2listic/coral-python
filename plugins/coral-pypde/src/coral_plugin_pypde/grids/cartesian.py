import ast

from pde import UnitGrid, CartesianGrid

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

    def __init__(self, bounds: str):
        bc = ast.literal_eval(bounds)
        self.grid = CartesianGrid(bc, 32)

        
    
