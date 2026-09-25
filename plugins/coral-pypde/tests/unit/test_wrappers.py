"""The wrapper classes, constructed directly — no solver, no simulation.

Constructing any of these is milliseconds: a grid is an allocation, a field is one random draw, and
the trackers only open their output file. What costs real time is
``PyPDEDiffusionPDE.solve``, exercised once behind ``slow`` in ``system/test_graphs_run.py``.
"""

from coral_plugin_pypde import (
    PyPDEDiffusionPDE,
    PyPDEFileStorage,
    PyPDEMovie,
    PyPDEPlotTracker,
    PyPDEScalarField,
    PyPDEUnitGrid,
)
from pde import DiffusionPDE, PlotTracker, ScalarField, UnitGrid
from pde.storage.base import StorageTracker
from pde.visualization.movies import Movie


class TestUnitGrid:
    """Two scalar ports standing in for py-pde's shape sequence."""

    def test_it_holds_a_unit_grid_of_the_given_shape(self):
        """GIVEN two side lengths
        WHEN a PyPDEUnitGrid is constructed
        THEN it holds a py-pde UnitGrid with exactly that shape, in that order."""
        grid = PyPDEUnitGrid(8, 4)

        assert isinstance(grid.grid, UnitGrid)
        assert tuple(grid.grid.shape) == (8, 4)


class TestScalarField:
    """The initial condition, and the private path a solved field comes back through."""

    def test_it_holds_a_random_field_on_the_given_grid(self):
        """GIVEN a grid and a value range
        WHEN a PyPDEScalarField is constructed
        THEN it holds a ScalarField on that same grid, with every value inside the range."""
        grid = PyPDEUnitGrid(8, 8)

        field = PyPDEScalarField(grid, 0.2, 0.3)

        assert isinstance(field.field, ScalarField)
        assert field.field.grid is grid.grid
        assert field.field.data.min() >= 0.2
        assert field.field.data.max() <= 0.3

    def test_holding_wraps_an_existing_field_untouched(self):
        """GIVEN a field py-pde already produced
        WHEN it is wrapped with the private ``_holding``
        THEN the wrapper carries that very object.

        This is how ``solve`` returns its result as a typed node output. The public constructor
        cannot do it: its job is to *draw a random field*, so routing a solved one through it would
        throw the solution away."""
        grid = PyPDEUnitGrid(4, 4)
        original = ScalarField(grid.grid, 7.0)

        wrapped = PyPDEScalarField._holding(original)

        assert isinstance(wrapped, PyPDEScalarField)
        assert wrapped.field is original


class TestFileStorage:
    """The HDF5 sink and the tracker that feeds it."""

    def test_it_keeps_its_filename_and_exposes_a_tracker(self, tmp_path):
        """GIVEN a filename, a write mode and a schedule
        WHEN a PyPDEFileStorage is constructed
        THEN it remembers the filename and holds a ready StorageTracker.

        The tracker is built at construction rather than at solve time, so the graph's storage node
        is complete on its own and ``solve`` only has to collect it."""
        storage = PyPDEFileStorage(str(tmp_path / "out.hdf5"), "truncate", 1.0)

        assert storage.filename.endswith("out.hdf5")
        assert isinstance(storage.tracker, StorageTracker)


class TestMovie:
    """The mp4 sink."""

    def test_it_holds_a_movie_for_the_given_file(self, tmp_path):
        """GIVEN a filename and rendering settings
        WHEN a PyPDEMovie is constructed
        THEN it holds a py-pde Movie pointed at that file."""
        movie = PyPDEMovie(str(tmp_path / "out.mp4"), 3, 100, 6000)

        assert isinstance(movie.movie, Movie)
        assert movie.movie.filename.endswith("out.mp4")

    def test_the_bitrate_is_forwarded_as_a_writer_keyword(self, tmp_path):
        """GIVEN a bitrate
        WHEN a PyPDEMovie is constructed
        THEN it lands in the keywords py-pde hands to matplotlib's FFMpegWriter.

        ``bitrate`` is deliberately a port even though ``Movie`` has no such parameter — this asserts
        the forwarding that makes that legitimate, rather than it being silently swallowed."""
        movie = PyPDEMovie(str(tmp_path / "out.mp4"), 3, 100, 6000)

        assert movie.movie.kwargs["bitrate"] == 6000


class TestPlotTracker:
    """The frame-drawing tracker, and the movie handle ``solve`` needs afterwards."""

    def test_it_holds_the_raw_movie_and_a_plot_tracker(self, tmp_path):
        """GIVEN a movie wrapper and a schedule
        WHEN a PyPDEPlotTracker is constructed
        THEN it holds a PlotTracker and the *same* Movie object the wrapper carries.

        Identity matters: the movie holds its file open until told the last frame is drawn, and
        ``solve`` closes it through this attribute. A copy would leave a truncated mp4."""
        movie = PyPDEMovie(str(tmp_path / "out.mp4"), 3, 100, 6000)

        plot = PyPDEPlotTracker(movie, 1.0)

        assert plot.movie is movie.movie
        assert isinstance(plot.tracker, PlotTracker)


class TestDiffusionPDE:
    """The equation itself — its ``solve`` is the one thing left to the slow test."""

    def test_it_holds_a_diffusion_equation_with_the_given_diffusivity(self):
        """GIVEN a diffusivity
        WHEN a PyPDEDiffusionPDE is constructed
        THEN it holds a py-pde DiffusionPDE carrying that value."""
        equation = PyPDEDiffusionPDE(0.1)

        assert isinstance(equation.equation, DiffusionPDE)
        assert equation.equation.diffusivity == 0.1
