#!/usr/bin/env python

# Examples taken from:
# http://www.mathworks.com/access/helpdesk/help/techdoc/ref/isosurface.html and
# http://www.mathworks.com/access/helpdesk/help/techdoc/visualize/f5-3653.html
import scitools.globaldata; scitools.globaldata.DEBUG = 1
from scitools.easyviz import *
from scitools.easyviz.vtk_new_ import *

setp(interactive=True)
setp(show=False)

x, y, z, v = flow()

h = isosurface(x, y, z, v, -3)
# setp(h, 'FaceColor', 'red', 'EdgeColor', 'none')
# h.setp(opacity=.5)
shading('flat')
daspect([1, 1, 1])
view(3)
axis('tight')
# camlight()
# lighting('gouraud')
setp(show=True)
show()

# savefig('tmp_isosurf1a.eps')
# savefig('tmp_isosurf1a_lq.eps', vector_file=False)
# savefig('tmp_isosurf1a.png')
setp(show=False)
figure()
h = isosurface(x, y, z, v, 0)
# setp(hpatch,'FaceColor','red','EdgeColor','none')
shading('interp')
daspect([1, 4, 4])
view([-65, 20])
axis('tight')
setp(show=True)
show()
# camlight('left')
# setp(gcf,'Renderer','zbuffer');
# lighting('phong')
# show()


# savefig('tmp_isosurf1b.eps')
# savefig('tmp_isosurf1b_lq.eps', vector_file=False)
# savefig('tmp_isosurf1b.png')
