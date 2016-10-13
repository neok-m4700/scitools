#!/usr/bin/env python

"""
Demonstration of the quiver command in combination with other plotting
commands.
"""
import scitools.globaldata
scitools.globaldata.DEBUG = 1
scitools.globaldata.backend = 'vtk_new'

from scitools.std import *

setp(interactive=False, show=False)

xv, yv = ndgrid(linspace(-5, 5, 81), linspace(-5, 5, 81))
values = sin(sqrt(xv**2 + yv**2))

pcolor(xv, yv, values, shading='interp')

# create a coarser grid for the gradient field:
xv, yv = ndgrid(linspace(-5, 5, 21), linspace(-5, 5, 21), sparse=True)
values = sin(sqrt(xv**2 + yv**2))

# compute the gradient field:
uu, vv = gradient(values)

hold('on')
quiver(xv, yv, uu, vv, 'filled', 'k', axis=[-6, 6, -6, 6])

# savefig('quiver2a.eps')
savefig('quiver2a_m2.png', magnification=2)

figure()
contour(xv, yv, values, 15, hold=True)
quiver(xv, yv, uu, vv, axis=[-6, 6, -6, 6])

# savefig('quiver2b.eps')
savefig('quiver2b_m2.png', magnification=2)

setp(interactive=True, show=True)
showfigs()
