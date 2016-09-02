#!/usr/bin/env python

# Example taken from:
# http://www.mathworks.com/access/helpdesk/help/techdoc/visualize/f5-3371.html
import scitools.globaldata; scitools.globaldata.DEBUG = 1; scitools.globaldata.backend = 'vtk_new'
from scitools.easyviz import *
from scipy import io

setp(interactive=False, show=False)

mri = io.loadmat('mri_matlab_v6.mat')
D = mri['D']
D = squeeze(D)

# print(D.nonzero())

image_num = 8
# xmin, xmax = xlim()
# ymin, ymax = ylim()
# print(xmin, xmax)
# print(ymin, ymax)

# Displaying a 2-D Contour Slice:
contourslice(D, [], [], image_num, indexing='xy')
axis('ij')

daspect([1, 1, 1])
colormap('viridis')
show()


print('..... before save')
setp(interactive=True, show=True); plt.mainloop(); exit(0)
# buggy script !!, exit for now ...
# problem with vtkOpenGLTexture
# vtkOpenGLTexture

savefig('tmp_contourslice2a.eps')

savefig('tmp_contourslice2a.png')
print('..... after save')

figure()
BUG = 1
print('..... before contour, after figure()')

phandles = contourslice(D, [], [], [1, 12, 19, 27 - BUG], 8, indexing='xy')
view(3)
axis('tight')

# set(phandles,'LineWidth',2)
setp(phandles, linewidth=4)
show()

print('..... there')
savefig('tmp_contourslice2b.eps')
savefig('tmp_contourslice2b.png')

plt.mainloop()
