# %%
from phi.flow import *

# %%
domain = Box(x=100, y=100)

inflow_rate = 0.2
inflow_x = 55
obstacle_x = 50

# %%
obstacle = Cuboid(vec(x=obstacle_x, y=60), half_size=vec(x=15, y=10))

# Define absorption and emission zones on opposite sides of the obstacle
# Absorption zone: bottom face of the obstacle
absorption_zone = Box(x=(obstacle_x - 15, obstacle_x + 15), y=(50 - 2, 50))  # Just below obstacle

# Emission zone: top face of the obstacle  
emission_zone = Box(x=(obstacle_x - 15, obstacle_x + 15), y=(70, 70 + 2))  # Just above obstacle

inflow = Sphere(x=inflow_x, y=9.5, radius=5)
plot(obstacle, inflow, absorption_zone, emission_zone, overlay='args')

# %%
# Transfer efficiency (how much of absorbed smoke is emitted)
transfer_rate = 0.8

@jit_compile
def step(v, s, p, absorbed_smoke, dt=1.):
    s = advect.mac_cormack(s, v, dt) + inflow_rate * resample(inflow, to=s, soft=True)
    
    # Get masks
    absorption_mask = resample(absorption_zone, to=s, soft=True)
    emission_mask = resample(emission_zone, to=s, soft=True)
    
    # Calculate total smoke to absorb (sum over spatial dims)
    smoke_to_absorb = s * absorption_mask
    total_absorbed = math.sum(smoke_to_absorb.values, dim=s.shape.spatial)
    
    # Remove from absorption zone
    s = s - smoke_to_absorb * transfer_rate
    
    # Calculate emission normalization factor
    emission_sum = math.sum(emission_mask.values, dim=s.shape.spatial) + 1e-8
    # print(f'{emission_sum=}')
    
    # Add to emission zone (normalized so mass is conserved)
    s = s + (total_absorbed * transfer_rate / emission_sum) * emission_mask
    
    # Fluid dynamics
    buoyancy = resample(s * (0, 0.1), to=v)
    v = advect.semi_lagrangian(v, v, dt) + buoyancy * dt
    v, p = fluid.make_incompressible(v, obstacle, Solve('scipy-direct', 1e-1, x0=p))
    
    return v, s, p, absorbed_smoke

v0 = StaggeredGrid(0, 0, domain, x=64, y=64)
smoke0 = CenteredGrid(0, ZERO_GRADIENT, domain, x=200, y=200)

v_trj, s_trj, p_trj, _ = iterate(step, batch(time=100), v0, smoke0, None, 0., dt=.5, substeps=3)

# %%
animSmoke = plot(obstacle, inflow, s_trj, animate='time', overlay='args')
animPressure = plot(obstacle, inflow, p_trj, animate='time', overlay='args')
animVelocity = plot(obstacle, inflow, v_trj, animate='time', overlay='args')
animSmoke.save('one_obstacle_absorb.gif')
animSmoke.save('one_obstacle_absorb.mp4', writer='ffmpeg', fps=15, dpi=150)
animPressure.save('one_obstacle_absorb_pressure.mp4', writer='ffmpeg', fps=15, dpi=150)
animVelocity.save('one_obstacle_absorb_velocity.mp4', writer='ffmpeg', fps=15, dpi=150)