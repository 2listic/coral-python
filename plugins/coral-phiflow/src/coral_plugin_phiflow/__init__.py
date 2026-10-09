"""coral-plugin-phiflow — PhiFlow physics-simulation wrappers.

Subclasses the coral-core ``Plugin`` contract; registered under the
``coral.plugins`` entry-point group as ``phiflow``.

PhiFlow is a hard dependency of this distribution, so the import below is
unconditional: a broken install fails loud with ``ImportError`` instead of
silently registering nothing. Lazy discovery guarantees this module is only
imported when ``phiflow`` is actually selected.
"""

from typing import Any, Dict, Tuple

from coral_core import Plugin
from .geom._box import PhiFlowBox, PhiFlowCuboid
from .geom._spere import PhiFlowSphere
from .field._grid import PhiFlowStaggeredGrid, PhiFlowCenteredGrid

from .custom import phiflow_iterate, phiflow_plot_and_save, phiflow_union

__all__ = ["PhiFlowPlugin"]


class PhiFlowPlugin(Plugin):
    """PhiFlow physics-simulation wrappers."""

    def get_functions(self) -> Dict[str, Any]:
        """Return PhiFlow function definitions"""
        return {
            "phiflow_iterate": phiflow_iterate,
            "phiflow_plot_and_save": phiflow_plot_and_save,
            "phiflow_union": phiflow_union,
        }

    def get_classes(self) -> Dict[str, Any]:
        """Return PhiFlow class definitions"""
        return {
            "PhiFlowBox": PhiFlowBox,
            "PhiFlowSphere": PhiFlowSphere,
            "PhiFlowStaggeredGrid": PhiFlowStaggeredGrid,
            "PhiFlowCenteredGrid": PhiFlowCenteredGrid,
            "PhiFlowCuboid": PhiFlowCuboid,
        }
