from pde import DiffusionPDE

from ..fields.scalar import PyPDEScalarField
from ..storage.file import PyPDEFileStorage
from ..trackers.trackers import PyPDEPlotTracker

class PyPDEDiffusionPDE:
    """Wrapper for the diffusion equation."""

    def __init__(self, diffusivity: float):
        self.equation = DiffusionPDE(diffusivity=diffusivity)

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

