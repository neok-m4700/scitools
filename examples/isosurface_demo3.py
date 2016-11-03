#!/usr/bin/env python

# Example taken from:
# http://www.mathworks.com/access/helpdesk/help/techdoc/visualize/f5-7858.html
import scitools.globaldata
scitools.globaldata.DEBUG = False
scitools.globaldata.backend = 'vtk_new'
from scitools.easyviz import *
from scipy import io
import numpy as np

setp(interactive=False)

# Create an Isosurface:
wind = io.loadmat('wind_matlab_v6.mat')
x, y, z = wind['x'], wind['y'], wind['z']
u, v, w = wind['u'], wind['v'], wind['w']

sx, sy, sz = ndgrid([80] * 36, seq(20, 55, 1), [5] * 36, sparse=True)

wind_speed = np.sqrt(u**2 + v**2 + w**2)

hiso = isosurface(x, y, z, wind_speed, 40, indexing='xy', iwidget=True)
# isonormals(x,y,z,wind_speed,hiso)
# set(hiso,'FaceColor','red','EdgeColor','none');
hold('on')
shading('interp')

# Add Isocaps to the Isosurface:
# hcap = patch(isocaps(x,y,z,wind_speed,40),...
#    'FaceColor','interp',...
#    'EdgeColor','none');
try:
    colormap(hsv())
except:
    pass

# Create First Set of Cones:
daspect([1, 1, 1])
# [f verts] = reducepatch(isosurface(x,y,z,wind_speed,30),0.07);
isosurface(x, y, z, wind_speed, 30, indexing='xy', iwidget=True)
# h1 = coneplot(x,y,z,u,v,w,verts(:,1),verts(:,2),verts(:,3),3);
# set(h1,'FaceColor','blue','EdgeColor','none');

# Create Second Set of Cones:
# xrange = linspace(min(x(:)),max(x(:)),10);
# yrange = linspace(min(y(:)),max(y(:)),10);
# zrange = 3:4:15;
# [cx,cy,cz] = ndgrid(xrange,yrange,zrange);
# h2 = coneplot(x,y,z,u,v,w,cx,cy,cz,2);
# set(h2,'FaceColor','green','EdgeColor','none');

# Define the View:
axis('tight')
box('on')
camproj('perspective')
camzoom(1.25)
view(65, 45)

# Add Lighting:
# camlight(-45,45)
# set(gcf,'Renderer','zbuffer');
# lighting phong
# set(hcap,'AmbientStrength',.6)

plt.mainloop()

# input('Press Return key to quit: ')
