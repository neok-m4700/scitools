import scitools.globaldata; scitools.globaldata.backend = 'vtk_new'
from scitools.easyviz import *
setp(show=False)

xv, yv = ndgrid(linspace(-2, 2, 41), linspace(-1, 1, 41))
for ext in ('png', 'tiff', 'png', 'jpg', 'bmp', 'pnm'):  # ps, eps not working for now - pnm neither
    for n, t in enumerate(linspace(0, 4, 15)):
        values = exp(-0.2 * t) * exp(-(2 * (xv - t + 1)**2 + 10 * yv**2))
        surf(xv, yv, values, colormap=hot(24), colorbar='on',
             savefig='tmp_{:03d}.{}'.format(n, ext),
             zlim=[0, 1], caxis=[0, 1])

# Note: this demo is very slow in matplotlib (3D)
