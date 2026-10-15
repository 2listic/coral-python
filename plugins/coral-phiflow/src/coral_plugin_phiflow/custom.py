from typing import Any, Tuple

from phi.flow import (
    # Classes
    Solve,
    Sphere,
    # Modules
    advect,
    batch,
    fluid,
    iterate,
    # Functions
    jit_compile,
    plot,
    resample,
    union,
)

from .field._grid import PhiFlowCenteredGrid, PhiFlowStaggeredGrid


def phiflow_iterate(
    velocity_grid: Any,
    smoke_grid: Any,
    time_steps: int,
    dt: float,
    substeps: int,
    obstacles: Any = None,
) -> Tuple[Any, Any, Any]:
    """Run multiple simulation steps using PhiFlow iterate"""
    v0 = (
        velocity_grid.get_grid()
        if isinstance(velocity_grid, PhiFlowStaggeredGrid)
        else velocity_grid
    )
    smoke0 = smoke_grid.get_grid() if isinstance(smoke_grid, PhiFlowCenteredGrid) else smoke_grid

    # Extract raw obstacle geometry from wrapper if needed
    if obstacles is not None:
        if hasattr(obstacles, "get_cuboid"):
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
        v, p = fluid.make_incompressible(v, obstacle_geom, Solve("scipy-direct", 1e-3, x0=p))
        return v, s, p

    v_trj, s_trj, p_trj = iterate(
        step, batch(time=time_steps), v0, smoke0, None, dt=dt, substeps=substeps
    )
    print(
        f"phiflow_iterate executed: time_steps={time_steps}, dt={dt}, substeps={substeps}, obstacles={'Yes' if obstacles is not None else 'No'}"
    )
    return v_trj, s_trj, p_trj


def phiflow_plot_and_save(
    smoke_trajectory: Any,
    output_filename: str,
    frame_time: int,
    fps: int,
    dpi: int,
    obstacles: Any = None,
) -> Any:
    """Plot smoke trajectory and save as animation"""
    # Extract raw obstacle geometry from wrapper if needed
    if obstacles is not None:
        if hasattr(obstacles, "get_cuboid"):
            obstacle_geom = obstacles.get_cuboid()
        else:
            obstacle_geom = obstacles
        # Plot with obstacles overlay
        anim = plot(
            obstacle_geom,
            smoke_trajectory,
            animate="time",
            overlay="args",
            frame_time=frame_time,
            show_color_bar=False,
        )
    else:
        # Plot without obstacles
        anim = plot(smoke_trajectory, animate="time", frame_time=frame_time, show_color_bar=False)

    anim.save(output_filename, writer="ffmpeg", fps=fps, dpi=dpi)
    print(f"phiflow_plot_and_save: saved to {output_filename} (fps={fps}, dpi={dpi})")
    return anim


def phiflow_union(
    geom1: Any,
    geom2: Any = None,
    geom3: Any = None,
    geom4: Any = None,
    geom5: Any = None,
    geom6: Any = None,
) -> Any:
    """Combine 2-6 geometries into a union"""
    geometries = [geom1, geom2, geom3, geom4, geom5, geom6]
    geometries = [g for g in geometries if g is not None]

    if len(geometries) < 2:
        raise ValueError("phiflow_union requires at least 2 geometries")

    # Extract raw objects from wrappers
    raw_geometries = []
    for g in geometries:
        if hasattr(g, "get_cuboid"):
            raw_geometries.append(g.get_cuboid())
        elif hasattr(g, "get_sphere"):
            raw_geometries.append(g.get_sphere())
        elif hasattr(g, "get_box"):
            raw_geometries.append(g.get_box())
        else:
            raw_geometries.append(g)

    result = union(*raw_geometries)
    print(f"phiflow_union: combined {len(raw_geometries)} geometries")
    return result
