from ast import literal_eval

from .obstacle import ObstacleDiffusionPDE
from ..grids.cartesian import PyPDECartesianGrid
from ..fields.scalar import PyPDEScalarField
from ..storage.file import PyPDEFileStorage
from ..trackers.trackers import PyPDEPlotTracker


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

    def _build_mask(self, grid):
        xC, yC = literal_eval(self.center)
        x, y = grid.grid.cell_coords[..., 0], grid.grid.cell_coords[..., 1]
        circle = (x - xC)**2 + (y - yC)**2 < self.radius**2
        self.mask = circle


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

    def _build_mask(self, grid):
        xC, yC = literal_eval(self.center)
        L1, L2 = literal_eval(self.sides)
        x, y = grid.grid.cell_coords[..., 0], grid.grid.cell_coords[..., 1]
        rectangle = (abs(x - xC) < L1) & (abs(y - yC) < L2)
        self.mask = rectangle


class PyPDEObstacleDiffusionPDE:
    """Wrapper for the custom obstacle diffusion equation."""

    def __init__(
            self,
            diffusivity: float,
            dx: float,
            grid: PyPDECartesianGrid,
            source: PyPDEShape,
            absorber: PyPDEShape,
            obstacle: PyPDEShape,
    ):
        self.grid = grid
        source._build_mask(self.grid)
        absorber._build_mask(self.grid)
        obstacle._build_mask(self.grid)
        self.source = source
        self.absorber = absorber
        self.obstacle = obstacle
        self.equation = ObstacleDiffusionPDE(diffusivity, dx, self.source, self.absorber, self.obstacle)

    def get_initial_condition(self) -> PyPDEScalarField:
        state = self.equation.get_initial_state(self.grid.grid)
        field = PyPDEScalarField(field_type="field", data=state)
        return field

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
