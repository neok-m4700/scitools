#!/usr/bin/env python

"""
Demonstration of the quiver command.
"""
import scitools.globaldata
scitools.globaldata.DEBUG = 1
scitools.globaldata.backend = 'vtk_new'

from scitools.std import *

setp(interactive=False, show=False)

# Plot the vector field F(x,y)=(-y,x):
xv, yv = ndgrid(np.linspace(-1, 1, 11), np.linspace(-1, 1, 11), sparse=False)
quiver(xv, yv, -yv, xv, 3)
axis('equal')
axis([-1, 1, -1, 1])
title('The vector field F(x,y)=(-y,x)')

# savefig('quiver1a.eps', color=True)
savefig('quiver1a.png', color=True)

figure()
# Now, turn off automatic scaling:
quiver(xv, yv, -yv, xv, 0, axis=[-1, 1, -1, 1])

# savefig('quiver1b.eps', color=True)
savefig('quiver1b.png', color=True)

figure()
# Plot the gradient field of the function f(x,y)=x**3-3x-2y**2:
xv, yv = ndgrid(np.linspace(-2, 2, 21), np.linspace(-1, 1, 11), sparse=False)
values = xv**3 - 3 * xv - 2 * yv**2
dx, dy = np.gradient(values, .2, .1)
quiver(xv, yv, dx, dy, axis='equal', xmin=-2, xmax=2, ymin=-1, ymax=1,
       title='The gradient vector field of f(x,y)=x**3-3x-2y**2')

# savefig('quiver1c.eps', color=True)
savefig('quiver1c.png', color=True)

showfigs(interactive=True, show=True)
