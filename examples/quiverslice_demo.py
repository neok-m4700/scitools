import scitools.globaldata
scitools.globaldata.DEBUG = 1
scitools.globaldata.backend = 'vtk_new'

from scitools.std import *
from scipy import io
setp(interactive=False, show=False)

wind = io.loadmat('wind_matlab_v6.mat')
x, y, z, u, v, w = wind['x'], wind['y'], wind['z'], wind['u'], wind['v'], wind['w']

figure()
quiverslice(x, y, z, u, v, w, [20], [], [12], arrowscale=.8, cone_resolution=4)
view(3)

savefig('quiver4a_m2.png', magnification=2)

plt.mainloop(interactive=True, show=True)
