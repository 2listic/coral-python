"""
Simple diffusion equation with I/O
==================================

This example solves a simple diffusion equation in two dimensions
and saves it using py-pde built-in saving methods.

Adapted from `simple.py` and `trajectory_io.py` in py-pde examples.
"""

import pde

grid = pde.UnitGrid([32, 32])  # generate grid
state = pde.ScalarField.random_uniform(grid, 0.2, 0.3)  # generate initial condition

outHDF5 = 'pypde/examples/output/out.hdf5'
outMP4 = 'pypde/examples/output/out.mp4'

writer = pde.FileStorage(outHDF5, write_mode="truncate")
tracker_write = writer.tracker(1) # create tracker which writes to hdf5

from pde.visualization.movies import Movie

movie = Movie(outMP4, framerate=3, dpi=200, bitrate=6000)
tracker_plot = pde.PlotTracker(movie=movie) # create movie tracker

trackers = [tracker_write, tracker_plot]
eq = pde.DiffusionPDE(diffusivity=0.1)  # define the pde
eq.solve(state, t_range=20, tracker=trackers)
movie.save()
# result = eq.solve(state, t_range=10)
# result.plot()
