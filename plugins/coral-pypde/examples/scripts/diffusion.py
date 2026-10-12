"""
Simple diffusion equation with I/O
==================================

This example solves a simple diffusion equation in two dimensions
and saves it using py-pde built-in saving methods.

Adapted from `simple.py` and `trajectory_io.py` in py-pde examples:
https://github.com/zwicker-group/py-pde/blob/master/examples/simple_pdes/simple.py
https://github.com/zwicker-group/py-pde/blob/master/examples/output/trajectory_io.py
"""

import pde

from pde.visualization.movies import Movie

# generate grid and initial condition
grid = pde.UnitGrid([32, 32])
state = pde.ScalarField.random_uniform(grid, 0.2, 0.3)

outHDF5 = 'pypde/examples/output/out.hdf5'
outMP4 = 'pypde/examples/output/out.mp4'

# create tracker which writes to hdf5
writer = pde.FileStorage(outHDF5, write_mode="truncate")
tracker_write = writer.tracker(1)

# create movie tracker which outputs a .mp4
movie = Movie(outMP4, framerate=3, dpi=200, bitrate=6000)
tracker_plot = pde.PlotTracker(movie=movie)

# define the pde, then solve it, writing to hdf5
trackers = [tracker_write, tracker_plot]
eq = pde.DiffusionPDE(diffusivity=0.1)
eq.solve(state, t_range=20, tracker=trackers)

# save the movie
movie.save()
# result = eq.solve(state, t_range=10)
# result.plot()
