import copy

from pde import PlotTracker

from ..visualization.movies import PyPDEMovie


class PyPDEPlotTracker:
    """Wrapper for a PlotTracker drawing frames into a movie.

    Keeps the raw movie too: it holds the file open until told the last frame has been drawn,
    which is what ``PyPDEDiffusionPDE.solve`` does once the solver returns. ``interrupts`` is
    this tracker's own schedule, independent of the storage's.

    The movie kept is a copy of the one given, which is a read input: drawing frames modifies a
    movie. A py-pde ``Movie`` opens its writer only at the first frame, so the copy is unstarted.
    """

    def __init__(self, movie: PyPDEMovie, interrupts: float):
        self.movie = copy.copy(movie.movie)
        self.tracker = PlotTracker(interrupts, movie=self.movie)
