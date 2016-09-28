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

x = zeros(data.GetNumberOfPoints())
y, z = x.copy(), x.copy()

for _ in range(data.GetNumberOfPoints()):
    x[_], y[_], z[_] = data.GetPoint(_)

# print(type(data))
# print(type(data.GetPointData()))
v_vtk = data.GetPointData().GetArray(0)

# convert to numpy array, we have to reshape for a 3D array
v = vtk_to_numpy(v_vtk).reshape(shape)
x, y, z = (_.reshape(shape) for _ in (x, y, z))

# print(x)
# print(v)

h = threshold(x, y, z, v, v.copy() + 100)
daspect([1, 1, 1])
view(3)
axis('tight')

plt.mainloop(show=True)
