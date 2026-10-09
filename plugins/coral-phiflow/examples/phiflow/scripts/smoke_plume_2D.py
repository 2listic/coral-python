"""Example script based on https://github.com/tum-pbs/PhiFlow/blob/master/examples/grids/Smoke_Plume.ipynb
This is the backend equivalent of the coral-python workflow smoke_plume_2D.json
"""

from phi.flow import *

domain = Box(x=100, y=100)
inflow = Sphere(x=50, y=9.5, radius=5)
inflow_rate = 0.2

@jit_compile
def step(v, s, p, dt):
    s = advect.mac_cormack(s, v, dt) + inflow_rate * resample(inflow, to=s, soft=True)
    buoyancy = resample(s * (0, 0.1), to=v)
    v = advect.semi_lagrangian(v, v, dt) + buoyancy * dt
    v, p = fluid.make_incompressible(v, (), Solve('scipy-direct', 1e-3, x0=p))
    return v, s, p

v0 = StaggeredGrid(0, 0, domain, x=64, y=64)
smoke0 = CenteredGrid(0, ZERO_GRADIENT, domain, x=200, y=200)
v_trj, s_trj, p_trj = iterate(step, batch(time=50), v0, smoke0, None, dt=.5, substeps=3)

anim = plot(s_trj, animate='time', frame_time=80, show_color_bar=False)
anim.save('scipy-direct.mp4', writer='ffmpeg', fps=15, dpi=150)
