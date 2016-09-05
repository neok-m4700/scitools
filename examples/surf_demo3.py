import scitools.globaldata; scitools.globaldata.DEBUG = 1; scitools.globaldata.backend = 'vtk_new'
from scitools.easyviz import *
from scitools.std import *

xv, yv = ndgrid(linspace(-2, 2, 21), linspace(-1, 1, 11))
values = xv**2 * yv - 2 * yv
setp(show=False)
subplot(221); surf(values)
subplot(222); surf(xv, yv, values, shading='flat')
subplot(223); surf(values, shading='interp')
subplot(224); surfc(values, clevels=10, clabels=True, filled=True)  # add contours beneath the surface
setp(show=True)
show()

plt.mainloop()
