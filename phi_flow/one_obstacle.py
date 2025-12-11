# %%
# %pip install phiflow
# from phi.jax.flow import *
# from phi.torch.flow import *
from phi.flow import *  # If JAX is not installed. You can use phi.torch or phi.tf as well.

# %%
domain = Box(x=100, y=100)

inflow_rate = 0.2
inflow_x = 55
obstacle_x = 50

# print(obstacle_x)

# %%
obstacle = Cuboid(vec(x=obstacle_x, y=60), half_size=vec(x=15, y=10))

inflow = Sphere(x=inflow_x, y=9.5, radius=5)
plot(obstacle, inflow, overlay='args')

# %%
@jit_compile
def step(v, s, p, dt=1.):
    s = advect.mac_cormack(s, v, dt) + inflow_rate * resample(inflow, to=s, soft=True)
    buoyancy = resample(s * (0, 0.1), to=v)
    v = advect.semi_lagrangian(v, v, dt) + buoyancy * dt
    v, p = fluid.make_incompressible(v, obstacle, Solve('scipy-direct', 1e-1, x0=p))
    return v, s, p

v0 = StaggeredGrid(0, 0, domain, x=64, y=64)
smoke0 = CenteredGrid(0, ZERO_GRADIENT, domain, x=200, y=200)

v_trj, s_trj, p_trj = iterate(step, batch(time=100), v0, smoke0, None, dt=.5, substeps=3)

# %%
anim = plot(obstacle, inflow, s_trj, animate='time', overlay='args')
anim.save('obstacle.gif')
anim.save('simulation.mp4', writer='ffmpeg', fps=15, dpi=150)



# %%
