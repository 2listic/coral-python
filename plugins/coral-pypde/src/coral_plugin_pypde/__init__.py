"""coral-plugin-pypde — py-pde PDE-solver wrappers.

Every node type is declared on :data:`plugin`, the ``coral_core.Plugin`` instance registered
under the ``coral.plugins`` entry-point group as ``pypde``.

py-pde is a hard dependency of this distribution, so its import is unconditional: a broken
install fails loud with ``ImportError`` instead of silently registering nothing.

Every port is annotated with a *wrapper* type rather than ``Any``, so the graph's
edge-type check can judge a py-pde workflow before the solver starts: a grid wired where a
field belongs is refused while the graph is being constructed, not after a simulation has run.
"""

from coral_core import Plugin

from .fields.scalar import PyPDEScalarField
from .grids.base import PyPDEGridBase
from .grids.cartesian import PyPDECartesianGrid, PyPDEUnitGrid
from .pdes.custom import PyPDECircle, PyPDEObstacleDiffusionPDE, PyPDERectangle, PyPDEShape
from .pdes.diffusion import PyPDEDiffusionPDE
from .pdes.laplace import pypde_solve_poisson_equation
from .storage.file import PyPDEFileStorage
from .trackers.trackers import PyPDEPlotTracker
from .visualization.movies import PyPDEMovie

__all__ = [
    "PyPDECartesianGrid",
    "PyPDECircle",
    "PyPDEDiffusionPDE",
    "PyPDEFileStorage",
    "PyPDEGridBase",
    "PyPDEMovie",
    "PyPDEObstacleDiffusionPDE",
    "PyPDEPlotTracker",
    "PyPDERectangle",
    "PyPDEScalarField",
    "PyPDEShape",
    "PyPDEUnitGrid",
    "plugin",
    "pypde_solve_poisson_equation",
]

#: This plugin: the entry point's target, on which every node type below is declared.
plugin = Plugin()

plugin.cls(PyPDEGridBase)
plugin.cls(PyPDEUnitGrid)
plugin.cls(PyPDECartesianGrid)

plugin.cls(PyPDEScalarField)
plugin.method(PyPDEScalarField.plot)
plugin.method(PyPDEScalarField.to_file)

plugin.cls(PyPDEFileStorage)
plugin.cls(PyPDEMovie)
plugin.cls(PyPDEPlotTracker)

plugin.cls(PyPDEDiffusionPDE)
plugin.method(PyPDEDiffusionPDE.solve)

plugin.cls(PyPDEShape)
plugin.cls(PyPDECircle)
plugin.cls(PyPDERectangle)

plugin.cls(PyPDEObstacleDiffusionPDE)
plugin.method(PyPDEObstacleDiffusionPDE.get_initial_condition)
plugin.method(PyPDEObstacleDiffusionPDE.solve)

plugin.function(pypde_solve_poisson_equation)
