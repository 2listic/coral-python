from typing import Any, Dict

# PyPDE imports - external Python library
try:
    from pde import (
        # Classes
        UnitGrid, ScalarField, FileStorage, PlotTracker, DiffusionPDE,
        # Functions
        #
        # Modules
        visualization,
        # Constants
        #
    )
    AVAILABLE = True
except ImportError:
    AVAILABLE = False
    print("Warning: PhiFlow not available. PhiFlow functions will not be registered.")


if AVAILABLE:

    class PyPDEUnitGrid:
        """Wrapper for """
        # def __init__(self, side: list):
        #     self.grid = UnitGrid(side)

        def __init__(self, x: int, y: int):
            # self.grid = UnitGrid(side)
            self.grid = UnitGrid([x, y])

        def get_grid(self) -> Any:
            return self.grid

    class PyPDEScalarField:
        """Wrapper for """
        def __init__(self):
            # micmat: I don't understand this mechanic of Python
            self.scalarfield = ScalarField

        def get_state(self, grid: Any, x: float, y: float) -> Any:
            return self.scalarfield.random_uniform(grid, x, y)

    class PyPDEFileStorage:
        """Wrapper for """
        def __init__(self, filename: str, write_mode: str):
            self.filestorage = FileStorage(filename, write_mode=write_mode)

        def get_tracker(self, interrupts: int) -> Any:
            return self.filestorage.tracker(interrupts)

    class PyPDEMovie:
        """Wrapper for """
        def __init__(self, filename: str, framerate: int, dpi: int, bitrate: int):
            self.movie = visualization.movies.Movie(filename, framerate=framerate, dpi=dpi, bitrate=bitrate)

        def get_movie(self) -> Any:
            return self.movie

    class PyPDEPlotTracker:
        """Wrapper for """
        def __init__(self, movie: Any):
            self.plottracker = PlotTracker(movie=movie)

        def get_plottracker(self) -> Any:
            return self.plottracker

    class PyPDEDiffusionPDE:
        """Wrapper for """
        def __init__(self, diffusivity: float):
            self.diffusionpde = DiffusionPDE(diffusivity=diffusivity)

        def solve(self, state: Any, t_range: int, tracker: Any):
            self.diffusionpde.solve(state, t_range=t_range, tracker=tracker)

            # for tr in tracker:
            #     if isinstance(tr, visualization.movies.Movie):
            #         tr.save()

            # the movie tracker needs to be closed after the simulation has ended
            # for technicalities explained in the backend
            if isinstance(tracker, visualization.movies.Movie):
                tracker.save()

    # def write_field_h5(smoke_trajectory: Any, output_filename: str) -> Any:
    #     """Save smoke trajectory as dataset in .h5 file"""
    #     with h5py.File("simulation.h5", "w") as f:
    #         grp = f.create_group(f"Trajectory")
    #         grp["smoke"] = smoke_trajectory.numpy()
    #     return 
                
def get_functions() -> Dict[str, Any]:
    """Return function definitions"""
    return {}

def get_classes() -> Dict[str, Any]:
    """Return class definitions"""
    return {
        "PyPDEUnitGrid": PyPDEUnitGrid,
        "PyPDEScalarField": PyPDEScalarField,
        "PyPDEFileStorage": PyPDEFileStorage,
        "PyPDEMovie": PyPDEMovie,
        "PyPDEPlotTracker": PyPDEPlotTracker,
        "PyPDEDiffusionPDE": PyPDEDiffusionPDE,
    }
