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

from .grids.cartesian import PyPDEUnitGrid
from .fields.scalar import PyPDEScalarField
from .storage.file import PyPDEFileStorage
from .visualization.movies import PyPDEMovie
from .pdes.diffusion import PyPDEDiffusionPDE
from .trackers.trackers import PyPDEPlotTracker


__all__ = [
    "PyPDEDiffusionPDE",
    "PyPDEFileStorage",
    "PyPDEMovie",
    "PyPDEPlotTracker",
    "PyPDEPlugin",
    "PyPDEScalarField",
    "PyPDEUnitGrid",
]


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
