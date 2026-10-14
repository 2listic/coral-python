import ast
from typing import Any
# from pde import CartesianGrid

from .pdes.obstacle import ObstacleDiffusionPDE
from .grids.cartesian import PyPDECartesianGrid
from .fields.scalar import PyPDEScalarField
from .storage.file import PyPDEFileStorage
from .trackers.trackers import PyPDEPlotTracker


class PyPDEShape:
    pass


class PyPDECircle(PyPDEShape):

    def __init__(
            self,
            radius: float,
            center: str,
            grid: PyPDECartesianGrid
    ) -> Any:
        xC, yC = ast.literal_eval(center)
        x, y = grid.grid.cell_coords[..., 0], grid.grid.cell_coords[..., 1]
        circle = (x - xC)**2 + (y - yC)**2 < radius**2
        self.mask = circle


# class PyPDERectangle(Shape):

#     def __init__(
#             self,
#             center: str,
#             sides: str,
#             grid: CartesianGrid
#     ) -> Any:
#         xC, yC = ast.literal_eval(center)
#         x, y = grid.cell_coords[..., 0], grid.cell_coords[..., 1]
#         circle = (x - xC)**2 + (y - yC)**2 < radius**2
#         return circle


class PyPDEObstacleDiffusionPDE:
    """Wrapper for the custom obstacle diffusion equation."""

    def __init__(
            self,
            diffusivity: float,
            dx: float,
            source: PyPDEShape,
            absorber: PyPDEShape,
            obstacle: PyPDEShape,
    ):
        self.equation = ObstacleDiffusionPDE(diffusivity, dx, source, absorber, obstacle)

    def get_initial_condition(
            self,
            grid
    ) -> PyPDEScalarField:
        state = self.equation.get_initial_state(grid.grid)
        field = PyPDEScalarField(field_type="array", data=state) 
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
