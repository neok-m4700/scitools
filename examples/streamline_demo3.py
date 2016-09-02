#!/usr/bin/env python

# Example taken from:
# http://www.mathworks.fr/access/helpdesk/help/techdoc/ref/streamparticles.html

import scitools.globaldata; scitools.globaldata.DEBUG = 1; scitools.globaldata.backend = 'vtk_new'
from scitools.easyviz import *
from scipy import io

wind = io.loadmat('wind_matlab_v6.mat')
x, y, z = wind['x'], wind['y'], wind['z']
u, v, w = wind['u'], wind['v'], wind['w']

setp(show=False)
setp(interactive=False)

sx, sy, sz = ndgrid([80] * 36, seq(20, 55, 1), [5] * 36)
sl = streamline(x, y, z, u, v, w, sx, sy, sz, maxlen=500)
ax = gca(); ax.setp(unit=False)
axis('tight')
view(30, 30)
daspect([1, 1, .125])
camproj('perspective')
camva(8)
box('on')

savefig('st_demo3_1.eps')

# alternative syntax:
sl = streamline(x, y, z, u, v, w, sx, sy, sz,
                axis='tight',
                view=(30, 30),
                daspect=[1, 1, .125],
                camproj='perspective',
                camva=8,
                box='on',
                maxlen=500
                )

ax = gca(); ax.setp(unit=False)

savefig('st_demo3_2.eps')
