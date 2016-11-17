import scitools.globaldata
scitools.globaldata.DEBUG = True
scitools.globaldata.backend = 'vtk_new'
from scitools.easyviz import *
import vtk
from vtk.util.numpy_support import vtk_to_numpy

setp(show=False)

reader = vtk.vtkStructuredPointsReader()
reader.SetFileName('ironProt.vtk')
reader.Update()

data = reader.GetOutput()
shape = data.GetDimensions()

x = np.zeros(data.GetNumberOfPoints())
y, z = x.copy(), x.copy()

for _ in range(data.GetNumberOfPoints()):
    x[_], y[_], z[_] = data.GetPoint(_)

v_vtk = data.GetPointData().GetArray(0)

# convert to numpy array, we have to reshape for a 3D array
v = vtk_to_numpy(v_vtk).reshape(shape)
x, y, z = (_.reshape(shape) for _ in (x, y, z))

# !! v.dtype=uint8: (0, 255), so c in in range (0, 255) too
c = v + 150
threshold(x, y, z, v, c)
colorbar()

plt.mainloop(show=True)
