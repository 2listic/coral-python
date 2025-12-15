
# %%
# !pip install --quiet phiflow
from phi.flow import *
# %%
smoke = CenteredGrid(0, extrapolation.BOUNDARY, x=32, y=40, bounds=Box(x=32, y=40))  # sampled at cell centers
velocity = StaggeredGrid(0, extrapolation.ZERO, x=32, y=40, bounds=Box(x=32, y=40))  # sampled in staggered form at face centers
# %%
INFLOW_LOCATION = tensor([(4, 5)], batch('inflow_loc'), channel(vector='x,y'))
INFLOW = 0.6 * CenteredGrid(Sphere(center=INFLOW_LOCATION, radius=3), extrapolation.BOUNDARY, x=32, y=40, bounds=Box(x=32, y=40))
# %%
print(f"Smoke: {smoke.shape}")
print(f"Velocity: {velocity.shape}")
print(f"Inflow: {INFLOW.shape}")
print(f"Inflow, spatial only: {INFLOW.shape.spatial}")
# %%
print(smoke.values)
print(velocity.values)
print(INFLOW.values)
# %%
smoke += INFLOW
buoyancy_force = smoke * (0, 0.5) @ velocity
velocity += buoyancy_force
velocity, _ = fluid.make_incompressible(velocity, (), Solve(rank_deficiency=0))

# vis.plot(smoke)
# %%
trajectory = [smoke]
for i in range(150):
  print(i, end=' ')
  smoke = advect.mac_cormack(smoke, velocity, dt=1) + INFLOW
  vis.savefig(f'./frame_{i:04d}.png', vis.plot(smoke))
  buoyancy_force = smoke * (0, 0.5) @ velocity
  velocity = advect.semi_lagrangian(velocity, velocity, dt=1) + buoyancy_force
  velocity, _ = fluid.make_incompressible(velocity, (), Solve(rank_deficiency=0))
  trajectory.append(smoke)
trajectory = field.stack(trajectory, batch('time'))
# video = vis.plot(trajectory, animate='time')
# vis.show(video)