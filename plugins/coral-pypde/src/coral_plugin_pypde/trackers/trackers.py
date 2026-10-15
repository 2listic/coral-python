from pde import PlotTracker

from ..visualization.movies import PyPDEMovie


class PyPDEPlotTracker:
    """Wrapper for a PlotTracker drawing frames into a movie.

    Keeps the raw movie too: it holds the file open until told the last frame has been drawn,
    which is what ``PyPDEDiffusionPDE.solve`` does once the solver returns. ``interrupts`` is
    this tracker's own schedule, independent of the storage's.
    """

    def __init__(self, movie: PyPDEMovie, interrupts: float):
        self.movie = movie.movie
        self.tracker = PlotTracker(interrupts, movie=self.movie)
