import scitools.globaldata
scitools.globaldata.DEBUG = 1
scitools.globaldata.backend = 'vtk_new'

from scitools.std import *
from scipy import io

setp(interactive=False, show=False)

xv, yv = ndgrid(linspace(-5, 5, 81), linspace(-5, 5, 81))
values = sin(sqrt(xv**2 + yv**2))

pcolor(xv, yv, values, shading='interp')

# create a coarser grid for the gradient field:
xv, yv = ndgrid(linspace(-5, 5, 21), linspace(-5, 5, 21), sparse=True)
values = sin(sqrt(xv**2 + yv**2))

# compute the gradient field:
uu, vv = gradient(values)

subplot(121)
quiver(xv, yv, uu, vv, 'filled', 'y', axis=[-6, 6, -6, 6])

subplot(122)
quiver(xv, yv, uu, vv, axis=[-6, 6, -6, 6])

savefig('quiver3a_m2.png', magnification=2)

wind = io.loadmat('wind_matlab_v6.mat')
x, y, z, u, v, w = wind['x'], wind['y'], wind['z'], wind['u'], wind['v'], wind['w']

figure()
subplot(121)
quiver3(x, y, z, u, v, w, cone_resolution=6)

subplot(122)
isosurface(x, y, z, v, 0)

savefig('quiver3b_m2.png', magnification=2)
