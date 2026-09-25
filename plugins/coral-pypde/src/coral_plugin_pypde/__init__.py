"""coral-plugin-pypde — py-pde PDE-solver wrappers.

Subclasses the coral-core ``Plugin`` contract; registered under the
``coral.plugins`` entry-point group as ``pypde``.

py-pde is a hard dependency of this distribution, so its import is unconditional: a broken
install fails loud with ``ImportError`` instead of silently registering nothing.

Every port below is annotated with a *wrapper* type rather than ``Any``, so the graph's
edge-type check can judge a py-pde workflow before the solver starts: a grid wired where a
field belongs is refused while the graph is being constructed, not after a simulation has run.
"""

from typing import Any, Dict

from coral_core import Plugin
from pde import DiffusionPDE, FileStorage, PlotTracker, ScalarField, UnitGrid
from pde.visualization.movies import Movie

__all__ = [
    "PyPDEDiffusionPDE",
    "PyPDEFileStorage",
    "PyPDEMovie",
    "PyPDEPlotTracker",
    "PyPDEPlugin",
    "PyPDEScalarField",
    "PyPDEUnitGrid",
]


class PyPDEUnitGrid:
    """Wrapper for a two-dimensional UnitGrid.

    py-pde takes the shape as a sequence; two scalar ports are what a graph can wire.
    """

    def __init__(self, x: int, y: int):
        self.grid = UnitGrid([x, y])


class PyPDEScalarField:
    """Wrapper for a ScalarField of uniform random values — a simulation's initial condition."""

    def __init__(self, grid: PyPDEUnitGrid, vmin: float, vmax: float):
        self.field = ScalarField.random_uniform(grid.grid, vmin, vmax)

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


class PyPDEFileStorage:
    """Wrapper for a FileStorage and the tracker that writes into it.

    ``interrupts`` is the schedule, in simulation time, on which a snapshot is written: ``1``
    stores one field per time unit.
    """

    def __init__(self, filename: str, write_mode: str, interrupts: float):
        self.filename = filename
        self.storage = FileStorage(filename, write_mode=write_mode)
        self.tracker = self.storage.tracker(interrupts)


class PyPDEMovie:
    """Wrapper for a Movie.

    ``bitrate`` is not a Movie parameter — py-pde forwards unknown keywords to matplotlib's
    FFMpegWriter, which is where the bit rate is set. Constructing one raises ``RuntimeError``
    when the ffmpeg binary is missing, which is the right moment to find out.
    """

    def __init__(self, filename: str, framerate: int, dpi: int, bitrate: int):
        self.movie = Movie(filename, framerate=framerate, dpi=dpi, bitrate=bitrate)


class PyPDEPlotTracker:
    """Wrapper for a PlotTracker drawing frames into a movie.

    Keeps the raw movie too: it holds the file open until told the last frame has been drawn,
    which is what ``PyPDEDiffusionPDE.solve`` does once the solver returns. ``interrupts`` is
    this tracker's own schedule, independent of the storage's.
    """

    def __init__(self, movie: PyPDEMovie, interrupts: float):
        self.movie = movie.movie
        self.tracker = PlotTracker(interrupts, movie=self.movie)


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


class PyPDEPlugin(Plugin):
    """py-pde PDE-solver wrappers."""

    def get_functions(self) -> Dict[str, Any]:
        """Return py-pde function definitions — this plugin declares none."""
        return {}

    def get_classes(self) -> Dict[str, Any]:
        """Return py-pde class definitions"""
        return {
            "PyPDEUnitGrid": PyPDEUnitGrid,
            "PyPDEScalarField": PyPDEScalarField,
            "PyPDEFileStorage": PyPDEFileStorage,
            "PyPDEMovie": PyPDEMovie,
            "PyPDEPlotTracker": PyPDEPlotTracker,
            "PyPDEDiffusionPDE": PyPDEDiffusionPDE,
        }
