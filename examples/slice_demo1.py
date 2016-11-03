#!/usr/bin/env python

# Example taken from:
# http://www.mathworks.com/access/helpdesk/help/techdoc/ref/slice.html
import scitools.globaldata
scitools.globaldata.DEBUG = True
scitools.globaldata.backend = 'vtk_new'
from scitools.easyviz import *
import numpy as np

setp(interactive=True)
setp(show=True)

BUG = .0001  # bug somewhere in _add_slice in vtk_.py
# BUG = 0
x, y, z = ndgrid(seq(-2, 2, .2), seq(-2, 2, .25), seq(-2, 2, .16), sparse=True)
v = x * np.exp(-x**2 - y**2 - z**2)
xslice = [-1.2, .8, 2 - BUG]
yslice = 2
zslice = [-2 + BUG, 0]
# xslice, zslice = ([] for _ in range(2))
slice_(x, y, z, v, xslice, yslice, zslice, grid='on', islice='implicit', iwidget='cube')

figure()
slice_(x, y, z, v, xslice, yslice, zslice, grid='on', islice='plane', iwidget='cube')


plt.mainloop()

# vtk 7.0.0 gl2psexporter is broken
# savefig('tmp_slice1.eps')
# savefig('tmp_slice1.png')
