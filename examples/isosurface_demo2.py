#!/usr/bin/env python

# Example taken from:
# http://www.mathworks.com/access/helpdesk/help/techdoc/visualize/f5-3371.html
import scitools.globaldata
scitools.globaldata.DEBUG = False
scitools.globaldata.backend = 'vtk_new'
from scitools.easyviz import *

from scipy import io

setp(interactive=False)

# Displaying an Isosurface:
mri = io.loadmat('mri_matlab_v6.mat')
D = mri['D']
D = np.squeeze(D)
print(D.shape)

# Ds = smooth3(D);

isosurface(D, 5, indexing='xy')
# hiso = isosurface(Ds,5),
#   'FaceColor',[1,.75,.65],...
#   'EdgeColor','none');
shading('interp')

# Adding an Isocap to Show a Cutaway Surface:
# hcap = patch(isocaps(D,5),...
#   'FaceColor','interp',...
#   'EdgeColor','none');
# colormap(map)

# Define the View:
view(45, 30)
axis('tight')
daspect([1, 1, .4])

# Add Lighting:
# lightangle(45,30);
# set(gcf,'Renderer','zbuffer'); lighting phong
# isonormals(Ds,hiso)
# set(hcap,'AmbientStrength',.6)
# set(hiso,'SpecularColorReflectance',0,'SpecularExponent',50)


# savefig('tmp_isosurf2a.eps')
# savefig('tmp_isosurf2a.png')

plt.mainloop()
