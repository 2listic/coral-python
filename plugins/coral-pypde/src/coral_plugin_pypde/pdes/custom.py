from ast import literal_eval

from ..fields.scalar import PyPDEScalarField
from ..grids.cartesian import PyPDECartesianGrid
from ..storage.file import PyPDEFileStorage
from ..trackers.trackers import PyPDEPlotTracker
from .obstacle import ObstacleDiffusionPDE


class PyPDEShape:
    pass


class PyPDECircle(PyPDEShape):
    """
    This class is used to define in coral a mask for a circular
    source/absorber/obstacle object to use in the PDE simulation
    """

    def __init__(
        self,
        radius: float,
        center: str,
    ):
        self.radius = radius
        self.center = center

    def _mask(self, grid):
        """The circle as a mask over the cells of ``grid``, a py-pde grid. The shape is left
        unchanged: it is a read input of the equation built from it."""
        xC, yC = literal_eval(self.center)
        x, y = grid.cell_coords[..., 0], grid.cell_coords[..., 1]
        return (x - xC) ** 2 + (y - yC) ** 2 < self.radius**2


class PyPDERectangle(PyPDEShape):
    """
    This class is used to define in coral a mask for a rectangular
    source/absorber/obstacle object to use in the PDE simulation
    """

    def __init__(
        self,
        center: str,
        sides: str,
    ):
        self.center = center
        self.sides = sides

    def _mask(self, grid):
        """The rectangle as a mask over the cells of ``grid``, a py-pde grid. The shape is left
        unchanged: it is a read input of the equation built from it."""
        xC, yC = literal_eval(self.center)
        L1, L2 = literal_eval(self.sides)
        x, y = grid.cell_coords[..., 0], grid.cell_coords[..., 1]
        return (abs(x - xC) < L1) & (abs(y - yC) < L2)


class PyPDEObstacleDiffusionPDE:
    """Wrapper for the custom obstacle diffusion equation.

    It keeps the py-pde grid, which py-pde treats as immutable, and the masks built from the
    shapes, never the shapes themselves.
    """

    def __init__(
        self,
        diffusivity: float,
        dx: float,
        grid: PyPDECartesianGrid,
        source: PyPDEShape,
        absorber: PyPDEShape,
        obstacle: PyPDEShape,
    ):
        self.grid = grid.grid
        self.equation = ObstacleDiffusionPDE(
            diffusivity,
            dx,
            source._mask(self.grid),
            absorber._mask(self.grid),
            obstacle._mask(self.grid),
        )

    def get_initial_condition(self) -> PyPDEScalarField:
        state = self.equation.get_initial_state(self.grid)
        return PyPDEScalarField._holding(state)

    def solve(
        self,
        state: PyPDEScalarField,
        t_range: int,
        storage: PyPDEFileStorage,
        plot: PyPDEPlotTracker,
    ) -> PyPDEScalarField:
        """Integrate to ``t_range``, feeding both trackers, and return the final state.

        The tracker list is assembled here rather than in the graph: coral cannot type a list's
        elements, so a ``list`` port would give up exactly the checking the wrapper types buy.
        """
        final = self.equation.solve(
            state.field, t_range=t_range, tracker=[storage.tracker, plot.tracker]
        )
        plot.movie.save()
        return PyPDEScalarField._holding(final)
