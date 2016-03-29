#!/usr/bin/env python

# Example taken from:
# http://www.mathworks.com/access/helpdesk/help/techdoc/visualize/f5-3371.html

from scitools.easyviz import *
from time import sleep
from scipy import io

setp(interactive=True)

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
colormap('default')
show()

savefig('tmp_contourslice2a.eps')
savefig('tmp_contourslice2a.png')

figure()
BUG = 1
phandles = contourslice(D, [], [], [1, 12, 19, 27 - BUG], 8, indexing='xy')
view(3)
axis('tight')
# set(phandles,'LineWidth',2)
setp(phandles, linewidth=4)
show()
# sleep(3)

savefig('tmp_contourslice2b.eps')
savefig('tmp_contourslice2b.png')


# input('Press Return key to quit: ')
