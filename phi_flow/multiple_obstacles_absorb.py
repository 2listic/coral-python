from phi.flow import *

domain = Box(x=100, y=100)

inflow_rate = 0.2
inflow_x = 55
inflow = Sphere(x=inflow_x, y=9.5, radius=5)

# Define obstacles with their inlet/outlet regions
# Left side obstacles (absorb from left, emit to right)
obstacle1 = Cuboid(vec(x=30, y=60), half_size=vec(x=10, y=10))
obstacle2 = Cuboid(vec(x=30, y=40), half_size=vec(x=10, y=10))
obstacle3 = Cuboid(vec(x=30, y=80), half_size=vec(x=10, y=10))

# Right side obstacles (absorb from right, emit to left)
obstacle4 = Cuboid(vec(x=80, y=60), half_size=vec(x=10, y=10))
obstacle5 = Cuboid(vec(x=80, y=40), half_size=vec(x=10, y=10))
obstacle6 = Cuboid(vec(x=80, y=80), half_size=vec(x=10, y=10))

obstacles = union(obstacle1, obstacle2, obstacle3, obstacle4, obstacle5, obstacle6)

# Define inlet regions (where smoke gets absorbed)
inlet1 = Cuboid(vec(x=20, y=60), half_size=vec(x=3, y=10))  # Left of obstacle1
inlet2 = Cuboid(vec(x=20, y=40), half_size=vec(x=3, y=10))  # Left of obstacle2
inlet3 = Cuboid(vec(x=20, y=80), half_size=vec(x=3, y=10))  # Left of obstacle3
inlet4 = Cuboid(vec(x=90, y=60), half_size=vec(x=3, y=10))  # Right of obstacle4
inlet5 = Cuboid(vec(x=90, y=40), half_size=vec(x=3, y=10))  # Right of obstacle5
inlet6 = Cuboid(vec(x=90, y=80), half_size=vec(x=3, y=10))  # Right of obstacle6

# Define outlet regions (where smoke gets emitted)
outlet1 = Cuboid(vec(x=40, y=60), half_size=vec(x=3, y=10))  # Right of obstacle1
outlet2 = Cuboid(vec(x=40, y=40), half_size=vec(x=3, y=10))  # Right of obstacle2
outlet3 = Cuboid(vec(x=40, y=80), half_size=vec(x=3, y=10))  # Right of obstacle3
outlet4 = Cuboid(vec(x=70, y=60), half_size=vec(x=3, y=10))  # Left of obstacle4
outlet5 = Cuboid(vec(x=70, y=40), half_size=vec(x=3, y=10))  # Left of obstacle5
outlet6 = Cuboid(vec(x=70, y=80), half_size=vec(x=3, y=10))  # Left of obstacle6

# Pair them up
inlet_outlet_pairs = [
    (inlet1, outlet1),
    (inlet2, outlet2),
    (inlet3, outlet3),
    (inlet4, outlet4),
    (inlet5, outlet5),
    (inlet6, outlet6),
]

# Absorption/emission efficiency (0-1)
transfer_rate = 0.8

@jit_compile
def step(v, s, p, dt=1.):
    # Normal smoke advection and source
    s = advect.mac_cormack(s, v, dt) + inflow_rate * resample(inflow, to=s)
    
    # Transfer smoke through obstacles
    for inlet, outlet in inlet_outlet_pairs:
        # Sample smoke concentration at inlet
        inlet_smoke = resample(s, to=inlet)
        
        # Calculate amount to transfer
        transfer_amount = inlet_smoke * transfer_rate
        
        # Remove from inlet
        s = s - resample(transfer_amount, to=s)
        
        # Add to outlet
        s = s + resample(transfer_amount, to=outlet) @ s
    
    # Rest of the simulation
    buoyancy = resample(s * (0, 0.1), to=v)
    v = advect.semi_lagrangian(v, v, dt) + buoyancy * dt
    v, p = fluid.make_incompressible(v, obstacles, Solve('scipy-direct', 1e-1, x0=p))
    
    return v, s, p

v0 = StaggeredGrid(0, 0, domain, x=64, y=64)
smoke0 = CenteredGrid(0, ZERO_GRADIENT, domain, x=200, y=200)

v_trj, s_trj, p_trj = iterate(step, batch(time=100), v0, smoke0, None, dt=.5, substeps=3)

anim = plot(obstacles, inflow, s_trj, animate='time', overlay='args')
anim.save('simulation.mp4', writer='ffmpeg', fps=15, dpi=150)