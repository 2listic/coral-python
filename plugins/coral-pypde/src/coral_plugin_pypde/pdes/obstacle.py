import numpy as np

from pde import PDEBase, ScalarField


class ObstacleDiffusionPDE(PDEBase):
    """
    Custom diffusion PDE that allows to simulate sources, absorbers and
    obstacles by masking the laplacian with logical arrays.

    * Sources (absorbers) are regions of fixed maximum (minimum) concentration
      that interact with the environment through their border
    * Obstacles have fixed (zero) concentration and do not interact.
    """

    def __init__(self, diffusivity, dx, source, absorber, obstacle):
        super().__init__()

        self.D = diffusivity
        self.dx = dx

        # Store masks as instance attributes
        self.source = source.mask
        self.absorber = absorber.mask
        self.obstacle = obstacle.mask

        # Only the obstacle blocks flux
        self.conducting = ~self.obstacle

        # All these regions have fixed concentrations
        self.fixed = self.obstacle | self.source | self.absorber

    def get_initial_state(self, grid):
        c0 = np.zeros_like(self.source)
        c0[self.source] = 1.0
        state = ScalarField(grid, c0)
        return state

    def masked_laplacian(self, c):
        """Apply mask to discrete laplacian according to obstacles."""
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
        Implement the ``evolution_rate`` method as requested by the parent class.
        This only allows to use the numpy backend.
        """
        c = state.data

        rate = self.D * self.masked_laplacian(c)
        rate[self.fixed] = 0.0

        return ScalarField(state.grid, rate)


