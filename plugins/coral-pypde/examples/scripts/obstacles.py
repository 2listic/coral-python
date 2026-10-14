import numpy as np
import matplotlib.pyplot as plt
import pde


class ObstacleDiffusionPDE(pde.PDEBase):
    """
    Custom diffusion PDE that allows to simulate sources, absorbers and
    obstacles by masking the laplacian with logical arrays.

    * Sources (absorbers) are regions of fixed maximum (minimum) concentration
      that interact with the environment through their border
    * Obstacles have fixed (zero) concentration and do not interact.
    """
    def __init__(self, diffusivity, dx, obstacle, source, absorber):
        super().__init__()

        self.D = diffusivity
        self.dx = dx

        # Store masks as instance attributes
        self.obstacle = obstacle
        self.source = source
        self.absorber = absorber

        # Only the obstacle blocks flux
        self.conducting = ~obstacle

        # All these regions have fixed concentrations
        self.fixed = obstacle | source | absorber

    def masked_laplacian(self, c):
        """Apply mask to discrete laplacian according to obstacle."""
        lap = np.zeros_like(c)
        h2 = self.dx**2

        # Axis 0
        valid = self.conducting[:-1, :] & self.conducting[1:, :]
        flux = np.zeros_like(valid, dtype=float)
        flux[valid] = (c[1:, :][valid] - c[:-1, :][valid]) / h2
        lap[:-1, :] += flux
        lap[1:, :] -= flux

        # Axis 1
        valid = self.conducting[:, :-1] & self.conducting[:, 1:]
        flux = np.zeros_like(valid, dtype=float)
        flux[valid] = (c[:, 1:][valid] - c[:, :-1][valid]) / h2
        lap[:, :-1] += flux
        lap[:, 1:] -= flux

        return lap

    def evolution_rate(self, state, t=0):
        """
        Implement the rate as requested by the parent class.
        This only allows to use the numpy backend.
        """
        c = state.data

        rate = self.D * self.masked_laplacian(c)
        rate[self.fixed] = 0.0

        return pde.ScalarField(state.grid, rate)


# --------------------------------------------------
# Grid and parameters
# --------------------------------------------------
N = 120
L = 1.0
D = 0.002
t_final = 1000

dx = L / N
dt = 0.15 * dx**2 / D

grid = pde.CartesianGrid([[0, L], [0, L]], [N, N], periodic=False)
# grid = pde.CartesianGrid([[-L/2, L/2], [-L/2, L/2]], [N, N], periodic=False)
x, y = grid.cell_coords[..., 0], grid.cell_coords[..., 1]

# --------------------------------------------------
# Define regions
# --------------------------------------------------
source = (x - 0.20)**2 + (y - 0.50)**2 < 0.07**2
absorber = (x - 0.80)**2 + (y - 0.50)**2 < 0.025**2
obstacle = (x - 0.50)**2 + (y - 0.50)**2 < 0.12**2

assert not np.any(obstacle & source)
assert not np.any(obstacle & absorber)
assert not np.any(source & absorber)

# --------------------------------------------------
# Initial condition
# --------------------------------------------------
c0 = np.zeros((N, N))
c0[source] = 1.0

state = pde.ScalarField(grid, c0)

# --------------------------------------------------
# Solve
# --------------------------------------------------
eq = ObstacleDiffusionPDE(
    diffusivity=D,
    dx=dx,
    obstacle=obstacle,
    source=source,
    absorber=absorber,
)

result = eq.solve(
    state,
    t_range=t_final,
    dt=dt,
    tracker=None,
)



sdfi

# --------------------------------------------------
# Plot
# --------------------------------------------------
fig, ax = plt.subplots(figsize=(7, 6))

im = ax.imshow(
    result.data.T,
    origin="lower",
    extent=(0, L, 0, L),
    cmap="viridis",
    vmin=0,
    vmax=1.0,
)

ax.contour(x.T, y.T, obstacle.T.astype(float),
           levels=[0.5], colors="white", linewidths=1.5)
ax.contour(x.T, y.T, source.T.astype(float),
           levels=[0.5], colors="red", linewidths=1.5)
ax.contour(x.T, y.T, absorber.T.astype(float),
           levels=[0.5], colors="cyan", linewidths=1.5)

fig.colorbar(im, ax=ax, label="Concentration")
ax.set_xlabel("x")
ax.set_ylabel("y")
ax.set_title("Diffusion with obstacle, source and absorber")
ax.set_aspect("equal")
plt.tight_layout()
plt.show()
plt.savefig('ciao.pdf')
