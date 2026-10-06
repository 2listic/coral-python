from pde import UnitGrid


class PyPDEUnitGrid:
    """Wrapper for a two-dimensional UnitGrid.

    py-pde takes the shape as a sequence; two scalar ports are what a graph can wire.
    """

    def __init__(self, x: int, y: int):
        self.grid = UnitGrid([x, y])
