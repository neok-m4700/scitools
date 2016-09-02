#!/usr/bin/env python

# Example taken from:
# http://www.mathworks.com/access/helpdesk/help/techdoc/ref/contourslice.html
import scitools.globaldata; scitools.globaldata.DEBUG = 1; scitools.globaldata.backend = 'vtk_new'
from scitools.easyviz import *

setp(show=False)
x, y, z, v = flow()
h = contourslice(x, y, z, v, seq(1, 9), [], [0], linspace(-8, 2, 10))
axis([0, 10, -3, 3, -3, 3])
daspect([1, 1, 1])
camva(24)
camproj('perspective')
campos([-3, -15, 5])
ax = gca()
ax.setp(fgcolor=(1, 1, 1), bgcolor=(0, 0, 0))
box('on')
view(3)  # because camva, camproj, and campos currently not working


setp(show=True)
show()

# savefig('tmp_contourslice1a.eps')
# savefig('tmp_contourslice1a.png')

figure()
# alternative syntax:
h = contourslice(x, y, z, v, seq(1, 9), [], [0], linspace(-8, 2, 10),
                 axis=[0, 10, -3, 3, -3, 3], daspect=[1, 1, 1],
                 camva=24, camproj='perspective', campos=[-3, -15, 5],
                 fgcolor=(1, 1, 1), bgcolor=(0, 0, 0),
                 box='on')

# savefig('tmp_contourslice1b.eps')
# savefig('tmp_contourslice1b.png')
plt.mainloop()
