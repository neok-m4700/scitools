import scitools.globaldata
scitools.globaldata.DEBUG = True
scitools.globaldata.VERBOSE = 1
scitools.globaldata.backend = 'vtk_new'

from scitools.std import *
from scipy import io
setp(interactive=False, show=False)

wind = io.loadmat('wind_matlab_v6.mat')
x, y, z, u, v, w = wind['x'], wind['y'], wind['z'], wind['u'], wind['v'], wind['w']

x, y, z, u, v, w = (np.swapaxes(_, 0, 1) for _ in (x, y, z, u, v, w))

# (41, 35, 15)
# 64 / 41 = 1.56 = dx
# 43 / 35 = 1.22 = dy
# 16 / 15 = 1.06 = dz
# diagonal cube = (1.56**2 + 1.22**2 + 1.06**2)**.5 = 2.24
# so we have to scale velocity vectors with this length
kw = dict(arrowscale=.9, cone_resolution=4)

print(x.min(), x.max(), y.min(), y.max(), z.min(), z.max())
print('u.shape', u.shape)
quiverslice(x, y, z, u, v, w, [20], [2], [12], **kw)
view(3)

savefig('quiver4a_m2_slice.png', magnification=2)

figure()
quiver3(x, y, z, u, v, w, **kw)
view(3)
savefig('quiver4a_m2.png', magnification=2)

plt.mainloop(interactive=True, show=True)
