#!/usr/bin/env python

# Example taken from:
# http://www.mathworks.com/access/helpdesk/help/techdoc/visualize/f5-3558.html

import scitools.globaldata
scitools.globaldata.backend = 'vtk_new'
scitools.globaldata.DEBUG = True
from scitools.easyviz import *
from time import sleep

# Investigate the Data:
x, y, z, v = flow()

xmin, ymin, zmin = x.min(), y.min(), z.min()
xmax, ymax, zmax = x.max(), y.max(), z.max()

setp(interactive=False)

# Create a Slice Plane at an Angle to the X-Axes:
hslice = surf(linspace(xmin, xmax, 100),
              linspace(ymin, ymax, 100),
              zeros((100, 100)))

# rotate(hslice,[-1,0,0],-45)
xd, yd, zd = hslice.getp('xdata'), hslice.getp('ydata'), hslice.getp('zdata')
# delete(hslice)

# Draw the Slice Planses:
# h = slice_(x,y,z,v,xd,yd,zd)
h = slice_(x, y, z, v, [], [], 0)
h.setp(diffuse=.8)
# h.set('FaceColor','interp',
#      'EdgeColor','none',
#      'DiffuseStrength',.8)

hold('on')
# hx = slice_(x,y,z,v,xmax,[],[])
hx = slice_(x, y, z, v, xmax - 0.001, [], [])
# set(hx,'FaceColor','interp','EdgeColor','none')

hy = slice_(x, y, z, v, [], ymax, [])
# set(hy,'FaceColor','interp','EdgeColor','none')

# hz = slice_(x,y,z,v,[],[],zmin)
hz = slice_(x, y, z, v, [], [], zmin + 0.001)
# set(hz,'FaceColor','interp','EdgeColor','none')

# Define the View:
daspect([1, 1, 1])
box('on')
grid('off')
view(-38.5, 16)
# camzoom(1.4)
camproj('perspective')

# Add Lighting and Specify Colors:
shading('interp')
# colormap(jet(24))
# lightangle(-45,45)

plt.mainloop(show=True, interactive=True)
# input("Press Return key to quit: ")
# print(plt._figs[1].getp('axes')[1].getp('plotitems'))
