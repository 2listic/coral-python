"""coral-plugin-phiflow — PhiFlow physics-simulation wrappers.

Every node type is declared on :data:`plugin`, the ``coral_core.Plugin`` instance registered
under the ``coral.plugins`` entry-point group as ``phiflow``.

PhiFlow is a hard dependency of this distribution, so the import below is
unconditional: a broken install fails loud with ``ImportError`` instead of
silently registering nothing. Lazy discovery guarantees this module is only
imported when ``phiflow`` is actually selected.
"""

from coral_core import Plugin

from .custom import phiflow_iterate, phiflow_plot_and_save, phiflow_union
from .field._grid import PhiFlowCenteredGrid, PhiFlowStaggeredGrid
from .geom._box import PhiFlowBox, PhiFlowCuboid
from .geom._spere import PhiFlowSphere

__all__ = ["plugin"]

#: This plugin: the entry point's target, on which every node type below is declared.
plugin = Plugin()

plugin.cls(PhiFlowBox)
plugin.method(PhiFlowBox.get_box, const=True)

plugin.cls(PhiFlowSphere)
plugin.method(PhiFlowSphere.get_sphere, const=True)

plugin.cls(PhiFlowStaggeredGrid)
plugin.method(PhiFlowStaggeredGrid.get_grid, const=True)

plugin.cls(PhiFlowCenteredGrid)
plugin.method(PhiFlowCenteredGrid.get_grid, const=True)

plugin.cls(PhiFlowCuboid)
plugin.method(PhiFlowCuboid.get_cuboid, const=True)

plugin.function(phiflow_iterate, outputs=("velocity", "smoke", "pressure"))
plugin.function(phiflow_plot_and_save)
plugin.function(phiflow_union)
