# %%
from phi.flow import *

# %%
values = math.random_uniform(spatial(x=50, y=10))

# %%
bounds = Box['x,y', 0:1, 0:1]

# %%
grid = StaggeredGrid(Noise(channel(vector=2)), extrapolation.BOUNDARY, bounds , x=50, y=10) * .1
grid2 = CenteredGrid(grid, 0, Box['x,y', -1:2, -1:2], x=20, y=100)

vis.plot([grid, grid2])
# vis.show(grid)
# vis.view(play=True, framerate=10)
# vis.plot(grid, save='./frames/frame_{:04d}.png')

# # %%
v = grid
vis.plot(v)
vs = [v]
for i in range(50):
  v = diffuse.explicit(v, .001, dt=.5, substeps=10)
  v = advect.semi_lagrangian(v, v, dt=.5)
  vs.append(v)
  figure = vis.plot(v)
  vis.savefig(f'./frames/frame_{i:04d}.png', figure)
  # vis.write_image(f'./frames/frame_{i:04d}.png', vs)
vis.plot([v.vector['x'] for v in vs], show_color_bar=False)



# %%
vis.show(vs[-1])  # Shows the final state
figure = vis.plot(vs[-1])  # Returns a matplotlib figure
vis.savefig('diffuson.png', figure)