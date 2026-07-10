# PhiFlow Simulations

This folder contains fluid dynamics simulations built with [PhiFlow](https://github.com/tum-pbs/PhiFlow), an open-source differentiable PDE solving framework from TU Munich. All scripts simulate **incompressible fluid flow** (smoke plumes rising through buoyancy) using the Navier-Stokes equations.

## Running

```bash
# From the project root, with the virtual environment activated
python phi_flow/one_obstacle_absorb.py
python phi_flow/multiple_obstacles.py
python phi_flow/examples/smoke_plume/smoke_plume.py

# Parallel simulations
python phi_flow/examples/parallel_simulations/parallel-simulation-script.py
```

Output files (`.gif`, `.mp4`) are generated in the script's working directory. `.mp4` export calls
matplotlib's `anim.save(..., writer='ffmpeg')`, which requires the `ffmpeg` binary installed and on
`PATH` (it's not a pip package). `.gif` export works without it.

## Physics Background

### The Navier-Stokes Equations

All scripts solve the incompressible Euler equations (Navier-Stokes without viscosity):

```
dv/dt + (v · ∇)v = -∇p + f       (momentum equation)
∇ · v = 0                         (incompressibility constraint)
```

Where **v** is the velocity field, **p** is pressure, and **f** represents external forces (buoyancy). Smoke density `s` is a passive scalar transported by velocity:

```
ds/dt + (v · ∇)s = sources
```

### Operator Splitting (Chorin Projection Method)

Every script follows the same **fractional-step** approach per timestep:

1. **Advect smoke** by the velocity field (transport the density)
2. **Add sources** (inflow of new smoke)
3. **Compute buoyancy** from smoke density (light fluid rises)
4. **Self-advect velocity** (nonlinear convection term)
5. **Pressure projection** — solve a Poisson equation to enforce ∇·v = 0

This is a standard method used in both research CFD and production visual effects.

## PhiFlow Concepts

### Grid Types

| Type | Purpose | Details |
|---|---|---|
| `CenteredGrid` | Scalar fields (smoke density, pressure) | Values stored at cell centers |
| `StaggeredGrid` | Velocity fields | Components stored at cell **faces** (MAC grid). This staggering prevents checkerboard pressure oscillations — a classic issue in collocated grids |

### Advection Schemes

**`advect.mac_cormack(field, velocity, dt)`** — Second-order MacCormack scheme:
1. Forward semi-Lagrangian step (trace particles backward along velocity, interpolate)
2. Backward step from the result
3. Correction: `result = forward + 0.5 * (original - backward)`
4. Clamping to prevent overshooting

Gives sharper smoke plumes than plain semi-Lagrangian while remaining unconditionally stable. Used for smoke advection where visual sharpness matters.

**`advect.semi_lagrangian(field, velocity, dt)`** — First-order semi-Lagrangian. For each grid point, trace backward along velocity by `dt`, interpolate the field at the departure point. Unconditionally stable but more diffusive. Used for velocity self-advection where stability matters more than sharpness.

### Pressure Projection

**`fluid.make_incompressible(velocity, obstacles, solver)`** — The most computationally expensive step. It:
1. Computes divergence: `div(v)`
2. Solves the Poisson equation: `∇²p = div(v)` (a large sparse linear system)
3. Corrects velocity: `v_new = v - ∇p`

The result is guaranteed divergence-free (mass-conserving). Available solvers:

| Solver | Method | Best for |
|---|---|---|
| `'scipy-direct'` | Sparse LU factorization | Small grids, exact solution |
| `'scipy-CG'` | Conjugate Gradient (iterative) | Large grids, GPU-friendly |

The `x0=p` parameter warm-starts from the previous pressure field, significantly reducing iterations.

### Buoyancy (Boussinesq Approximation)

```python
buoyancy = resample(s * (0, 0.1), to=v)
```

Models the Boussinesq approximation: smoke density `s` creates an upward force proportional to its concentration. The vector `(0, 0.1)` means zero horizontal force, `0.1 * s` vertical force. This is what makes the smoke rise and develop Kelvin-Helmholtz instabilities at the plume edges.

### Other Operations

- **`resample(geometry, to=grid, soft=True)`** — Converts geometric shapes to grid masks. `soft=True` gives fractional values for partially covered cells (anti-aliased boundaries).
- **`@jit_compile`** — JIT-compiles the step function. Traces the computation graph once, reuses the compiled version on subsequent calls.
- **`iterate(step, batch(time=N), ..., dt, substeps)`** — Runs the step function N times, collecting trajectories. `substeps=3` with `dt=0.5` means each frame actually performs 3 sub-iterations.
- **`union(...)`** — Merges multiple geometries into one for the pressure solver.

### Extrapolation (Boundary Conditions)

| Mode | Physics | Effect |
|---|---|---|
| `ZERO_GRADIENT` | Neumann (∂u/∂n = 0) | Values at boundary copy from nearest interior cell. Smoke slides along walls. |
| `extrapolation.ZERO` | Dirichlet (u = 0) | Values vanish at boundary. Used for velocity (open boundary). |
| `extrapolation.BOUNDARY` | Neumann-like | Similar to zero-gradient, copies boundary values. |

## Scripts

### `examples/smoke_plume/smoke_plume.py` — Baseline Smoke Plume

The simplest simulation. A spherical inflow source at the bottom center emits smoke that rises via buoyancy, with no obstacles. Demonstrates the core simulation pipeline.

- **Domain**: 100×100 units
- **Inflow**: `Sphere(x=50, y=9.5, radius=5)` — circular source near the bottom
- **Resolution**: 64×64 velocity, 200×200 smoke
- **Timesteps**: 50 frames, `dt=0.5`, 3 substeps each

### `multiple_obstacles.py` — Six-Obstacle Array

Buoyant plume deflected by 6 rectangular obstacles arranged in two columns:

```
Left column (x=30):     Right column (x=80):
  y=80: obstacle3         y=80: obstacle6
  y=60: obstacle1         y=60: obstacle4
  y=40: obstacle2         y=40: obstacle5
```

The obstacles create complex **vortex shedding** patterns (analogous to flow past a cylinder array). The pressure solver enforces zero normal velocity at each obstacle surface.

### `one_obstacle_absorb.py` — Obstacle with Absorption/Emission

The most physically involved script. A single obstacle absorbs smoke from below and re-emits it above, modeling a **porous or reactive surface**:

- **Absorption zone**: Thin strip (2 units) below the obstacle — removes smoke
- **Emission zone**: Thin strip (2 units) above the obstacle — re-emits absorbed smoke
- **Transfer rate**: 0.8 (80% efficiency — 20% is lost)
- **Mass conservation**: emission is normalized so total emitted = `transfer_rate × total_absorbed`:
  ```python
  s = s + (total_absorbed * transfer_rate / emission_sum) * emission_mask
  ```

Generates separate animations for smoke density, pressure field, and velocity field.

### `tutorial/tutorial_2.py` — Step-by-Step Smoke Simulation

Pedagogical version using an explicit Python loop (150 iterations) instead of `iterate()`. Shows each operation clearly:

```python
smoke = advect.mac_cormack(smoke, velocity, dt=1) + INFLOW
buoyancy_force = smoke * (0, 0.5) @ velocity       # @ resamples to velocity grid
velocity = advect.semi_lagrangian(velocity, velocity, dt=1) + buoyancy_force
velocity, _ = fluid.make_incompressible(velocity, ...)
```

The `@` operator is PhiFlow's syntax for resampling between grid types. Note the stronger buoyancy coefficient (0.5 vs 0.1 in other scripts). Saves individual PNG frames.

### `tutorial/pde_tutorial.py` — Diffusion + Advection

Demonstrates solving two fundamental PDEs on their own:

- **Diffusion**: `du/dt = ν∇²u` via `diffuse.explicit(v, 0.001, dt=0.5, substeps=10)`. The viscosity `ν = 0.001`. Multiple substeps are needed because explicit diffusion has a CFL stability limit: `dt < dx²/(2ν)`.
- **Advection**: velocity self-advects via semi-Lagrangian.

Initial condition is random noise on a staggered grid, which gradually smooths through diffusion.

### `examples/parallel_simulations/` — Batched Parallel Scenarios

Three variants of the same concept: running **multiple simulation scenarios simultaneously** using PhiFlow's batch dimensions:

```python
settings = batch(setting=3)
inflow_rate = tensor([.1, .2, .3], settings)     # 3 different inflow strengths
inflow_x = tensor([40, 50, 60], settings)         # 3 different source positions
obstacle_x = wrap([15, 50, 70], settings)          # 3 different obstacle positions
```

Every operation processes all 3 scenarios at once (vectorized). On GPU backends this maps to true SIMD parallelism.

| File | Solver | JIT | Timesteps |
|---|---|---|---|
| `parallel-simulation.py` | Custom Solve (tol 1e-3) | No | 100 |
| `parallel-simulation-script.py` | `scipy-direct` (tol 1e-1) | Yes | 300 |
| `parallel-simulation-torch.py` | `scipy-CG` (tol 1e-3) | No | 30 |

Note: `obstacle_x` uses `wrap()` instead of `tensor()` because obstacle geometry changes the sparsity pattern of the pressure Poisson matrix — different obstacle positions produce different blocked cells, affecting which matrix entries are nonzero.

## References

- **PhiFlow repository**: https://github.com/tum-pbs/PhiFlow
- **PhiFlow documentation**: https://tum-pbs.github.io/PhiFlow/
- **Fluids tutorial (video)**: https://youtu.be/YRi_c0v3HKs
- **Tensors and dimensions (video)**: https://youtu.be/4nYwL8ZZDK8
- **Neural networks with PhiFlow (video)**: https://youtu.be/aNigTqklCBc
- **API reference**: https://tum-pbs.github.io/PhiFlow/phi/
