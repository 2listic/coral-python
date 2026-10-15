"""The wrapper classes, constructed directly — no solver, no simulation.

Constructing any of these is milliseconds: a grid is an allocation, a field is one random draw, and
the trackers only open their output file. What costs real time is
``PyPDEDiffusionPDE.solve``, exercised once behind ``slow`` in ``system/test_graphs_run.py``.
"""

import numpy
import pytest
from coral_plugin_pypde import (
    PyPDECartesianGrid,
    PyPDECircle,
    PyPDEDiffusionPDE,
    PyPDEFileStorage,
    PyPDEGridBase,
    PyPDEMovie,
    PyPDEObstacleDiffusionPDE,
    PyPDEPlotTracker,
    PyPDERectangle,
    PyPDEScalarField,
    PyPDEUnitGrid,
)
from pde import CartesianGrid, DiffusionPDE, PlotTracker, ScalarField, UnitGrid
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


class TestCartesianGrid:
    """Bounds and shape written as Python literals: a graph has no port for a sequence."""

    def test_it_holds_a_cartesian_grid_with_the_given_bounds_and_shape(self):
        """GIVEN bounds and a shape, each written as a Python literal
        WHEN a PyPDECartesianGrid is constructed
        THEN it holds a py-pde CartesianGrid with exactly those bounds and that shape."""
        grid = PyPDECartesianGrid("[[0.0, 1.0], [0.0, 2.0]]", "[4, 8]")

        assert isinstance(grid.grid, CartesianGrid)
        assert tuple(grid.grid.shape) == (4, 8)
        assert grid.grid.axes_bounds == ((0.0, 1.0), (0.0, 2.0))


class TestGridBase:
    """The one type a field's ``grid`` port is annotated with."""

    def test_both_grids_are_grid_bases(self):
        """GIVEN one grid of each kind
        WHEN their types are checked
        THEN both are PyPDEGridBase, which is what lets either be wired into a field's ``grid``."""
        assert isinstance(PyPDEUnitGrid(4, 4), PyPDEGridBase)
        assert isinstance(PyPDECartesianGrid("[[0.0, 1.0]]", "8"), PyPDEGridBase)


class TestScalarField:
    """The initial condition, and the private path a solved field comes back through."""

    def test_it_holds_a_random_field_on_the_given_grid(self):
        """GIVEN a grid and a value range, as the ``random_uniform`` mode reads them
        WHEN a PyPDEScalarField is constructed
        THEN it holds a ScalarField on that same grid, with every value inside the range."""
        grid = PyPDEUnitGrid(8, 8)

        field = PyPDEScalarField(grid, "random_uniform", '{"vmin": 0.2, "vmax": 0.3}')

        assert isinstance(field.field, ScalarField)
        assert field.field.grid is grid.grid
        assert field.field.data.min() >= 0.2
        assert field.field.data.max() <= 0.3

    def test_a_constant_expression_fills_the_grid_with_it(self):
        """GIVEN a grid and the expression ``"1"``
        WHEN a PyPDEScalarField is constructed in the ``expression`` mode
        THEN it holds a ScalarField on that same grid, equal to 1 everywhere."""
        grid = PyPDECartesianGrid("[[0.0, 1.0]]", "32")

        field = PyPDEScalarField(grid, "expression", "1")

        assert field.field.grid is grid.grid
        assert numpy.all(field.field.data == 1.0)

    def test_an_expression_of_the_coordinates_varies_with_them(self):
        """GIVEN a grid and the expression ``"x"``
        WHEN a PyPDEScalarField is constructed in the ``expression`` mode
        THEN each cell holds its own x coordinate."""
        grid = PyPDECartesianGrid("[[0.0, 1.0]]", "32")

        field = PyPDEScalarField(grid, "expression", "x")

        numpy.testing.assert_allclose(field.field.data, grid.grid.cell_coords[..., 0])

    def test_an_unknown_field_type_is_refused(self):
        """GIVEN a field type that is none of the modes
        WHEN a PyPDEScalarField is constructed
        THEN it raises ValueError naming the field type, rather than holding no field."""
        with pytest.raises(ValueError, match="field_type"):
            PyPDEScalarField(PyPDEUnitGrid(4, 4), "constant", "1")

    def test_holding_wraps_an_existing_field_untouched(self):
        """GIVEN a field py-pde already produced
        WHEN it is wrapped with the private ``_holding``
        THEN the wrapper carries that very object.

        This is how ``solve`` returns its result as a typed node output. The public constructor
        cannot do it: its job is to *build* a field from a description, so routing a solved one
        through it would throw the solution away."""
        grid = PyPDEUnitGrid(4, 4)
        original = ScalarField(grid.grid, 7.0)

        wrapped = PyPDEScalarField._holding(original)

        assert isinstance(wrapped, PyPDEScalarField)
        assert wrapped.field is original


class TestScalarFieldOutputs:
    """The two sinks a field writes itself to, each restricted to one file format."""

    @pytest.fixture
    def field(self):
        """A small field that varies across its grid, so a written file has content to compare."""
        return PyPDEScalarField(PyPDECartesianGrid("[[0.0, 1.0]]", "8"), "expression", "x")

    def test_plot_writes_a_png(self, field, tmp_path):
        """GIVEN a field and a ``.png`` filename
        WHEN ``plot`` is called
        THEN the file is written and is not empty."""
        target = tmp_path / "field.png"

        field.plot(str(target))

        assert target.stat().st_size > 0

    def test_plot_refuses_any_other_format(self, field, tmp_path):
        """GIVEN a filename not ending in ``.png``
        WHEN ``plot`` is called
        THEN it raises ValueError and writes nothing."""
        target = tmp_path / "field.pdf"

        with pytest.raises(ValueError, match="png"):
            field.plot(str(target))
        assert not target.exists()

    def test_to_file_writes_an_h5_that_reads_back_equal(self, field, tmp_path):
        """GIVEN a field and a ``.h5`` filename
        WHEN ``to_file`` is called
        THEN the file reads back as a ScalarField holding the same data."""
        target = tmp_path / "field.h5"

        field.to_file(str(target))

        numpy.testing.assert_array_equal(ScalarField.from_file(str(target)).data, field.field.data)

    def test_to_file_refuses_any_other_format(self, field, tmp_path):
        """GIVEN a filename not ending in ``.h5``
        WHEN ``to_file`` is called
        THEN it raises ValueError and writes nothing."""
        target = tmp_path / "field.txt"

        with pytest.raises(ValueError, match="h5"):
            field.to_file(str(target))
        assert not target.exists()


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


class TestShapes:
    """A shape is geometry only; its mask is built on the grid the equation is given."""

    @pytest.fixture
    def grid(self):
        """A unit square of 20x20 cells: the point (0.5, 0.5) lies on a cell boundary in both axes,
        so a shape centred on it covers the same number of cells on each side."""
        return PyPDECartesianGrid("[[0.0, 1.0], [0.0, 1.0]]", "[20, 20]")

    def test_a_circle_masks_the_cells_around_its_center_only(self, grid):
        """GIVEN a circle centred in the square
        WHEN its mask is built on the grid
        THEN it covers the four cells around the centre, none of the corners, and is symmetric
        under swapping x and y and under mirroring either."""
        circle = PyPDECircle(0.25, "[0.5, 0.5]")

        circle._build_mask(grid)

        assert circle.mask.shape == (20, 20)
        assert circle.mask[9:11, 9:11].all()
        assert not circle.mask[[0, 0, -1, -1], [0, -1, 0, -1]].any()
        assert (circle.mask == circle.mask.T).all()
        assert (circle.mask == circle.mask[::-1, :]).all()

    def test_a_rectangle_masks_an_axis_aligned_rectangle_around_its_center(self, grid):
        """GIVEN a rectangle centred in the square, its second side the longer
        WHEN its mask is built on the grid
        THEN the masked cells fill their bounding box exactly, the box is centred on the centre,
        and it is longer along y than along x.

        Only the shape is asserted, not the size: what makes it a rectangle is that the cells form
        a full, axis-aligned box."""
        rectangle = PyPDERectangle("[0.5, 0.5]", "[0.1, 0.3]")

        rectangle._build_mask(grid)

        rows, cols = numpy.nonzero(rectangle.mask)
        box = rectangle.mask[rows.min() : rows.max() + 1, cols.min() : cols.max() + 1]
        assert box.all()
        assert rectangle.mask.sum() == box.size
        assert rows.min() + rows.max() == 19
        assert cols.min() + cols.max() == 19
        assert rows.max() - rows.min() < cols.max() - cols.min()


class TestObstacleDiffusionPDE:
    """The equation built from three shapes, and the initial state it derives from them."""

    def test_its_initial_condition_is_one_on_the_source_and_zero_elsewhere(self):
        """GIVEN an equation built from a source, an absorber and an obstacle that do not overlap
        WHEN its initial condition is asked for
        THEN it is a PyPDEScalarField on the equation's grid, 1 exactly on the source's cells and 0
        everywhere else."""
        grid = PyPDECartesianGrid("[[0.0, 1.0], [0.0, 1.0]]", "[20, 20]")
        source = PyPDECircle(0.1, "[0.2, 0.5]")
        absorber = PyPDECircle(0.1, "[0.8, 0.5]")
        obstacle = PyPDERectangle("[0.5, 0.5]", "[0.05, 0.2]")
        equation = PyPDEObstacleDiffusionPDE(0.002, 0.05, grid, source, absorber, obstacle)

        initial = equation.get_initial_condition()

        assert source.mask.any()
        assert isinstance(initial, PyPDEScalarField)
        assert initial.field.grid is grid.grid
        numpy.testing.assert_array_equal(initial.field.data, source.mask.astype(float))
