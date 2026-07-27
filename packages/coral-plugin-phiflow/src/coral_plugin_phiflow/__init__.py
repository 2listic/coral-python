"""coral-plugin-phiflow — PhiFlow physics-simulation wrappers.

Subclasses the coral-core ``Plugin`` contract; registered under the
``coral.plugins`` entry-point group as ``phiflow``.

Per D5, PhiFlow is a hard dependency of this distribution: the import below is
unconditional, so a broken install fails loud with ``ImportError`` instead of
silently registering nothing. Lazy discovery guarantees this module is only
imported when ``phiflow`` is actually selected.
"""

from typing import Any, Dict, Tuple

from coral_core import Plugin
from phi.flow import (
    # Classes
    Box, Sphere, Cuboid, StaggeredGrid, CenteredGrid, Solve,
    # Functions
    jit_compile, resample, iterate, plot, batch, vec, union,
    # Modules
    advect, fluid,
    # Constants
    ZERO_GRADIENT,
)

__all__ = ["PhiFlowPlugin"]


# PhiFlow wrapper classes and functions (simplified for smoke_plume.py example)

class PhiFlowBox:
    """Wrapper for Box domain"""
    def __init__(self, x: float, y: float):
        self.box = Box(x=x, y=y)
        print(f"PhiFlowBox created: x={x}, y={y}")

    def get_box(self) -> Any:
        return self.box


class PhiFlowSphere:
    """Wrapper for Sphere geometry"""
    def __init__(self, x: float, y: float, radius: float):
        self.sphere = Sphere(x=x, y=y, radius=radius)
        print(f"PhiFlowSphere created: x={x}, y={y}, radius={radius}")

    def get_sphere(self) -> Any:
        return self.sphere


class PhiFlowStaggeredGrid:
    """Wrapper for StaggeredGrid"""
    def __init__(self, domain_box: Any, resolution_x: int, resolution_y: int):
        if isinstance(domain_box, PhiFlowBox):
            domain = domain_box.get_box()
        else:
            domain = domain_box
        self.grid = StaggeredGrid(0, 0, domain, x=resolution_x, y=resolution_y)
        print(f"PhiFlowStaggeredGrid created: resolution={resolution_x}x{resolution_y}")

    def get_grid(self) -> Any:
        return self.grid


class PhiFlowCenteredGrid:
    """Wrapper for CenteredGrid"""
    def __init__(self, domain_box: Any, resolution_x: int, resolution_y: int):
        if isinstance(domain_box, PhiFlowBox):
            domain = domain_box.get_box()
        else:
            domain = domain_box
        self.grid = CenteredGrid(0, ZERO_GRADIENT, domain, x=resolution_x, y=resolution_y)
        print(f"PhiFlowCenteredGrid created: resolution={resolution_x}x{resolution_y}")

    def get_grid(self) -> Any:
        return self.grid


class PhiFlowCuboid:
    """Wrapper for Cuboid geometry"""
    def __init__(self, center_x: float, center_y: float, half_size_x: float, half_size_y: float):
        self.cuboid = Cuboid(vec(x=center_x, y=center_y), half_size=vec(x=half_size_x, y=half_size_y))
        print(f"PhiFlowCuboid created: center=({center_x}, {center_y}), half_size=({half_size_x}, {half_size_y})")

    def get_cuboid(self) -> Any:
        return self.cuboid


def phiflow_iterate(velocity_grid: Any, smoke_grid: Any, time_steps: int, dt: float, substeps: int, obstacles: Any = None) -> Tuple[Any, Any, Any]:
    """Run multiple simulation steps using PhiFlow iterate"""
    v0 = velocity_grid.get_grid() if isinstance(velocity_grid, PhiFlowStaggeredGrid) else velocity_grid
    smoke0 = smoke_grid.get_grid() if isinstance(smoke_grid, PhiFlowCenteredGrid) else smoke_grid

    # Extract raw obstacle geometry from wrapper if needed
    if obstacles is not None:
        if hasattr(obstacles, 'get_cuboid'):
            obstacle_geom = obstacles.get_cuboid()
        else:
            obstacle_geom = obstacles
    else:
        obstacle_geom = ()  # Empty tuple means no obstacles

    inflow = Sphere(x=50, y=9.5, radius=5)
    inflow_rate = 0.2

    @jit_compile
    def step(v, s, p, dt):
        s = advect.mac_cormack(s, v, dt) + inflow_rate * resample(inflow, to=s, soft=True)
        buoyancy = resample(s * (0, 0.1), to=v)
        v = advect.semi_lagrangian(v, v, dt) + buoyancy * dt
        v, p = fluid.make_incompressible(v, obstacle_geom, Solve('scipy-direct', 1e-3, x0=p))
        return v, s, p

    v_trj, s_trj, p_trj = iterate(step, batch(time=time_steps), v0, smoke0, None, dt=dt, substeps=substeps)
    print(f"phiflow_iterate executed: time_steps={time_steps}, dt={dt}, substeps={substeps}, obstacles={'Yes' if obstacles is not None else 'No'}")
    return v_trj, s_trj, p_trj


def phiflow_plot_and_save(smoke_trajectory: Any, output_filename: str, frame_time: int, fps: int, dpi: int, obstacles: Any = None) -> Any:
    """Plot smoke trajectory and save as animation"""
    # Extract raw obstacle geometry from wrapper if needed
    if obstacles is not None:
        if hasattr(obstacles, 'get_cuboid'):
            obstacle_geom = obstacles.get_cuboid()
        else:
            obstacle_geom = obstacles
        # Plot with obstacles overlay
        anim = plot(obstacle_geom, smoke_trajectory, animate='time', overlay='args', frame_time=frame_time, show_color_bar=False)
    else:
        # Plot without obstacles
        anim = plot(smoke_trajectory, animate='time', frame_time=frame_time, show_color_bar=False)

    anim.save(output_filename, writer='ffmpeg', fps=fps, dpi=dpi)
    print(f"phiflow_plot_and_save: saved to {output_filename} (fps={fps}, dpi={dpi})")
    return anim


def phiflow_union(geom1: Any, geom2: Any = None, geom3: Any = None, geom4: Any = None, geom5: Any = None, geom6: Any = None) -> Any:
    """Combine 2-6 geometries into a union"""
    geometries = [geom1, geom2, geom3, geom4, geom5, geom6]
    geometries = [g for g in geometries if g is not None]

    if len(geometries) < 2:
        raise ValueError("phiflow_union requires at least 2 geometries")

    # Extract raw objects from wrappers
    raw_geometries = []
    for g in geometries:
        if hasattr(g, 'get_cuboid'):
            raw_geometries.append(g.get_cuboid())
        elif hasattr(g, 'get_sphere'):
            raw_geometries.append(g.get_sphere())
        elif hasattr(g, 'get_box'):
            raw_geometries.append(g.get_box())
        else:
            raw_geometries.append(g)

    result = union(*raw_geometries)
    print(f"phiflow_union: combined {len(raw_geometries)} geometries")
    return result


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
