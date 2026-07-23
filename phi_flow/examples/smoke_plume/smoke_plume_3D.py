# from phi.jax.flow import *
# import phi.jax.flow as phi
# from phi.flow import *  # If JAX is not installed. You can use phi.torch or phi.tf as well.
import phi.flow as phi  # If JAX is not installed. You can use phi.torch or phi.tf as well.

import numpy as np
import h5py
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, FFMpegWriter
from matplotlib import cm, colors


domain = phi.Box(x=40, y=40, z=40)
inflow = phi.Sphere(x=20, y=20, z=20, radius=4)
inflow_rate = 0.2

@phi.jit_compile
def step(v, s, p, dt):
    s = phi.advect.mac_cormack(s, v, dt) + inflow_rate * phi.resample(inflow, to=s, soft=True)
    buoyancy = phi.resample(s * (0, 0.1, 0), to=v)
    v = phi.advect.semi_lagrangian(v, v, dt) + buoyancy * dt
    v, p = phi.fluid.make_incompressible(v, (), phi.Solve('scipy-direct', 1e-3, x0=p))
    # print(dir(v))
    # print(s.geometry)
    # ciao = s.numpy()
    # print(ciao.shape)
    # print(dir(p))
    return v, s, p

smoke0 = phi.CenteredGrid(0, phi.ZERO_GRADIENT, x=40, y=40, z=40, bounds=domain)
v0 = phi.StaggeredGrid(0, 0, x=16, y=16, z=16, bounds=domain)

n_steps = 10
v_trj, s_trj, p_trj = phi.iterate(step, phi.batch(time=n_steps), v0, smoke0, None, dt=0.5, substeps=3)

smoke = s_trj.numpy()

with h5py.File("simulation.h5", "w") as f:

    grp = f.create_group(f"Trajectory")
    grp["smoke"] = smoke

    
def animate_smoke_voxels(smoke, filename="smoke.mp4", fps=20, threshold=0.05):

    nt, nx, ny, nz = smoke.shape

    fig = plt.figure(figsize=(8, 8))
    ax = fig.add_subplot(111, projection="3d")

    norm = colors.Normalize(vmin=smoke.min(), vmax=smoke.max())
    cmap = cm.viridis

    def update(frame):
        ax.cla()
        data = smoke[frame]
        filled = data > threshold * data.max()
        facecolors = cmap(norm(data))
        ax.voxels(
            filled,
            facecolors=facecolors,
            edgecolor=None
        )
        ax.set_xlim(0, nx)
        ax.set_ylim(0, ny)
        ax.set_zlim(0, nz)
        ax.set_box_aspect((nx, ny, nz))
        ax.set_title(f"Frame {frame}")
        
    ani = FuncAnimation(
        fig,
        update,
        frames=nt,
        interval=1000/fps
    )
    writer = FFMpegWriter(fps=fps)
    ani.save(filename, writer=writer)
    plt.close(fig)
        
animate_smoke_voxels(smoke, threshold=0.1, filename="smoke.mp4", fps=1)
# anim = phi.plot(s_trj, animate='time', frame_time=1, show_color_bar=False)
# anim.save('scipy-direct.mp4', writer='ffmpeg', fps=1, dpi=150)
