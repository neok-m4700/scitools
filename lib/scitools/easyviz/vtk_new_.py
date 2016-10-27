'''
This is a template file for writing new backends. It is a fully functional
backend, but no output is produced. One can specify this backend by

  python somefile.py --SCITOOLS_easyviz_backend template

or one can specify the backend in the SciTools configuration file
scitools.cfg under the [easyviz] section

  [easyviz]
  backend = template

and then

  from scitools.std import *

or if just easyviz is needed

  from scitools.easyviz import *

When writing a new backend, one can copy this file to xxx_.py (note the
underscore), where 'xxx' is the name of the new backend. Then replace all
instances of 'template' with 'xxx' and start implementing the class
methods below. The most important methods are figure, _replot, and hardcopy.

REQUIREMENTS:

VTK >= 4.2
Python bindings for

Notes:

- filled contours (contourf) doesn't look good in VTK 5..

'''

from __future__ import print_function

import os
import readline  # see bugs.python.org/issue19884
import sys
from contextlib import contextmanager
import numba

import numpy as np
from enum import Enum
from scitools.globaldata import DEBUG, OPTIMIZATION, VERBOSE, VTK_BACKEND
from scitools.misc import check_if_module_exists
from util.vtkAlgorithm import VTKPythonAlgorithmBase
from vtk import *

from .colormaps import _cmaps
from .common import *
from .misc import _update_from_config_file

# change these to suit your needs.
major_minor = '.'.join(map(str, (sys.version_info.major, sys.version_info.minor)))
inc_dirs = [os.path.expandvars('$CONDA_PREFIX/include/vtk-7.0')]
lib_dirs = [os.path.expandvars('$CONDA_PREFIX/lib/python{}/site-packages'.format(major_minor)), '/usr/lib']

sys.path.extend(lib_dirs)
# print(sys.path)
# print(os.getcwd())

_vtk_options = dict(mesa=0, vtk_inc_dir=inc_dirs, vtk_lib_dir=lib_dirs)
_update_from_config_file(_vtk_options, section='vtk')

if _vtk_options['mesa']:
    _graphics_fact = vtkGraphicsFactory()
    _graphics_fact.SetOffScreenOnlyMode(1)
    _graphics_fact.SetUseMesaClasses(1)
    _imaging_fact = vtkImagingFactory()
    _imaging_fact.SetUseMesaClasses(1)
    del _graphics_fact
    del _imaging_fact


ENABLE, CACHE = OPTIMIZATION == 'numba', True

def jit(*args, **kwargs):
    def wrap(func):
        return numba.jit(func, cache=CACHE, **kwargs) if not __debug__ and ENABLE else func
    return wrap(*args) if args else wrap


def njit(*args, **kwargs):
    def wrap(func):
        return numba.jit(func, cache=CACHE, nopython=True, **kwargs) if not __debug__ and ENABLE else func
    return wrap(*args) if args else wrap


VTK_COORD_SYS = {0: 'VTK_DISPLAY', 1: 'VTK_NORMALIZED_DISPLAY', 2: 'VTK_VIEWPORT', 3: 'VTK_NORMALIZED_VIEWPORT', 4: 'VTK_VIEW', 5: 'VTK_WORLD', 6: 'VTK_USERDEFINED'}


def _print(*args, **kwargs):
    if DEBUG:
        print(*args, **kwargs)


@contextmanager
def _debug(*args):
    _print('[ ', ' '.join(map(str, args)), end=' ', sep='')
    yield
    _print(']', end=' ')

if 'qt' in VTK_BACKEND.lower():
    from PyQt4 import QtCore, QtGui

    from vtk.qt4.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
    from vtk.qt.QVTKRenderWindowInteractor import _qt_key_to_key_sym, _keysyms

    class _QVTKRenderWindowInteractor(vtk.qt4.QVTKRenderWindowInteractor.QVTKRenderWindowInteractor):

        def keyPressEvent(self, e, filtered=False):
            ctrl, shift = self._GetCtrlShift(e)
            key = str(e.text()) if e.key() < 256 else chr(0)

            keySym = _qt_key_to_key_sym(e.key())
            if shift and len(keySym) == 1 and keySym.isalpha():
                keySym = keySym.upper()

            mod = e.modifiers() if hasattr(e, 'modifiers') else self.__saveModifiers
            if mod & QtCore.Qt.KeypadModifier:
                keySym = 'kp_' + keySym

            # forward the event
            if filtered:
                self._Iren.SetEventInformationFlipY(self.__saveX, self.__saveY, ctrl, shift, key, 0, keySym)
                self._Iren.KeyPressEvent()
                self._Iren.CharEvent()
            # intercept the event and parse the content
            else:
                self.callback(e, ctrl, shift, widget=self, x=self.__saveX, y=self.__saveY, keysym=keySym)

else:
    try:
        import tkinter
    except:
        import Tkinter as tkinter
    try:
        import vtkTkRenderWidget
        import vtkTkRenderWindowInteractor
    except:
        from tk import vtkTkRenderWidget
        from tk import vtkTkRenderWindowInteractor


class _VTKFigure:

    def __init__(self, plt, width, height, title=''):
        self.backend = VTK_BACKEND.lower()
        self.plt = plt
        self.width = width
        self.height = height
        if 'tk' in self.backend:
            self.root = tkinter.Toplevel(plt._master)
            self.root.title(title)
            self.root.protocol('WM_DELETE_WINDOW', self.exit)
            self.root.minsize(200, 200)
            self.root.geometry('{}x{}'.format(width, height))
            self.root.withdraw()
            self.frame = tkinter.Frame(self.root)  # relief='sunken', bd=2
            self.frame.pack(side='top', fill='both', expand='true')
        else:
            self.root = QtGui.QMainWindow()
            self.root.setWindowTitle(title)
            self.root.closeEvent = lambda e: self.exit()
            self.root.resize(self.width, self.height)
            self.frame = QtGui.QFrame()
            self.vl = QtGui.QVBoxLayout()
        self._init()

    def _init(self):
        with _debug('_init'):
            if 'tk' in self.backend:
                self.vtkWidget = vtkTkRenderWindowInteractor.vtkTkRenderWindowInteractor(self.frame, width=self.width, height=self.height)
                self.vtkWidget.pack(expand='true', fill='both')
            else:
                self.vtkWidget = _QVTKRenderWindowInteractor(self.frame)  # this object inherits from QWidget
                self.vl.addWidget(self.vtkWidget)

            self.renwin = self.vtkWidget.GetRenderWindow()
            self.renwin.SetSize(self.width, self.height)
            self.iren = self.renwin.GetInteractor()
            # force trackball mode, see also vtkInteractorObserver::OnChar or vtk3DWidget
            self.iren.SetInteractorStyle(vtkInteractorStyleTrackballCamera())

            if 'tk' in self.backend:
                self.vtkWidget.focus_force()  # needed for the callback to work
                self.vtkWidget.update()

    def hard_reset(self):
        with _debug('hard reset'):
            # is calling del removing the window from memory, not only from namespace ?
            # for now this is the only way for the interactive widgets to work when issuing a replot ...
            # if we could avoid deleting the vtkWidget it'll be great ...
            self.clear()
            self._init()

    def soft_reset(self, axs=()):
        with _debug('soft reset'):
            for ax in axs:  # remove renderer associated to axis
                ren = getattr(ax, '_renderer', None)
                if ren and self.renwin.HasRenderer(ren):
                    self.renwin.RemoveRenderer(ren)

    def display(self, show):
        with _debug('display'):
            if show:
                if 'tk' in self.backend:
                    self.root.deiconify()  # Displays the window
                    self.root.update()
                else:
                    self.frame.setLayout(self.vl)
                    self.root.setCentralWidget(self.frame)
                    self.root.raise_()   # Raises this widget to the top of the parent widget's stack
                    self.root.show()  # Shows the widget and its child widgets

            self.iren.Initialize()
            self.render()

    def render(self):
        with _debug('render'):
            # full pipeline update (is it really necessary ??)
            if hasattr(self.plt, '_ax'):
                self.plt._ax._apd.Update()

            renderers = self.renwin.GetRenderers()  # first we render each of the axis renderers
            ren = renderers.GetFirstRenderer()

            while ren is not None:
                ren.Render()
                ren = renderers.GetNextItem()

            self.renwin.Render()  # render the complete scene

    def clear(self):
        with _debug('clear'):
            self.renwin.Finalize()  # call the internal cleanup method on VTK objects
            if self.iren:
                self.iren.TerminateApp()
                del self.iren
            del self.renwin
            if 'tk' in self.backend:
                self.root.withdraw()  # removes the window from the screen (without destroying it)
                self.vtkWidget.forget()
            else:
                pass
                # [self.vl.itemAt(_).widget().close() for _ in range(self.vl.count())]
                # self.root.hide()

    def exit(self):
        with _debug('exit'):
            self.clear()
            if 'tk' in self.backend:
                self.frame.forget()
            else:
                pass
                # self.vtkWidget.close() # will get destroyed throught the qt event mechanism
            self.plt.closefig(self)

    def set_size(self, width, height):
        if 'tk' in self.backend:
            self.root.geometry('{}x{}'.format(width, height))
            self.root.update()
        else:
            self.root.resize(width, height)

    def __str__(self):
        return '\n'.join(['{}:{}'.format(k, v) for (k, v) in self.__dict__.items()])


class vtkAlgorithmSource(VTKPythonAlgorithmBase):
    '''
    berkgeveci.github.io/2014/09/18/pipeline

    Vocable
    -------
    Extents: Extents are only applicable to structured datasets. An extent is a logical subset of a structured dataset defined by providing min and max IJK values (VOI).
    Pieces: Pieces are only applicable to unstructured datasets. A piece is a subset of an unstructured dataset. What a "piece" means is determined by the producer of such dataset.
    '''

    def __init__(self, data=None, outputType='vtkStructuredGrid'):
        try:
            iter(data)
            self._data = list(data)
        except:
            self._data = list([data])
        super().__init__(nInputPorts=0, nOutputPorts=len(self._data), outputType=outputType)
        self._exec = self.GetExecutive()

    def RequestInformation(self, request, inputVector, outputVector):
        for _ in range(self.GetNumberOfOutputPorts()):
            if hasattr(self._data[_], 'GetExtent'):
                'vtkPolyData does not have a method GetExtent !'
                outInfo = outputVector.GetInformationObject(_)
                __ = self._data[_].GetExtent()
                outInfo.Set(self._exec.WHOLE_EXTENT(), __, len(__))
        return 1

    def RequestData(self, request, inInfo, outInfo):
        for _ in range(self.GetNumberOfOutputPorts()):
            info = outInfo.GetInformationObject(_)
            opt = info.Get(vtkDataObject.DATA_OBJECT())
            opt.ShallowCopy(self._data[_])
        return 1

    def GetOutput(self, port=0):
        return self.GetOutputDataObject(port)


def vtkInteractiveWidget(parent, **kwargs):
    if 'boxwidget' in parent.lower():
        klass, plane = vtkBoxWidget, vtkPlanes()
    elif 'implicitplanewidget' in parent.lower():
        klass, plane = vtkImplicitPlaneWidget, vtkPlane()
    else:
        raise NotImplementedError('wrong type of parent: {}'.format(parent))

    class _vtkInteractiveWidget(klass):

        def __init__(self, plane, **kwargs):
            super().__init__()
            self.ax = kwargs.get('ax')
            self.fig = kwargs.get('fig')
            self._p = plane
            self._obs = []
            old = getattr(self.ax, '_iw', None)
            self._hs = getattr(old, '_hs', self.GetHandleSize() / 3)
            self._on = getattr(old, '_on', False)
            if isinstance(self, vtkBoxWidget):
                self._t = vtkTransform()
                if isinstance(old, vtkBoxWidget):
                    old.GetTransform(self._t)
            elif isinstance(self, vtkImplicitPlaneWidget):
                self._b = getattr(old, '_b', (-1, 1, -1, 1, -1, 1))
            if len(getattr(old, '_obs', [])) > 0:
                old._RemoveObservers()

            self.SetInteractor(self.fig._g.iren)
            # self.SetCurrentRenderer(self.ax._renderer)
            self.SetDefaultRenderer(self.ax._renderer)
            self.SetHandleSize(self._hs)
            self.SetPlaceFactor(1.01)
            self.SetInputConnection(kwargs.get('ic'))
            self.PlaceWidget()
            if isinstance(self, vtkBoxWidget):
                self.GetOutlineProperty().SetColor(self.ax.getp('axiscolor'))
                self.RotationEnabledOff()  # we want a bow aligned with the ax, so no rotation allowed
                self.SetTransform(self._t)
            elif isinstance(self, vtkImplicitPlaneWidget):
                [_.SetColor(self.ax.getp('axiscolor')) for _ in (self.GetOutlineProperty(), self.GetEdgesProperty())]
                self._pd = vtkPolyData()

        def _GetPlane(self):
            if isinstance(self, vtkBoxWidget):
                self.GetPlanes(self._p)
            elif isinstance(self, vtkImplicitPlaneWidget):
                self.GetPlane(self._p)

        def _RemoveObservers(self):
            try:
                [self.RemoveObserver(_) for _ in self._obs]
            except:
                pass

        def _AddObservers(self):
            for e, c in [('InteractionEvent', self.pw_interaction),
                         ('StartInteractionEvent', self.pw_start_interaction),
                         ('EndInteractionEvent', self.pw_end_interaction),
                         ('EnableEvent', self.pw_enable),
                         ('DisableEvent', self.pw_disable)]:
                self._obs.append(self.AddObserver(e, c))

        def _SaveWidget(self):
            if isinstance(self, vtkBoxWidget):
                self.GetTransform(self._t)
            elif isinstance(self, vtkImplicitPlaneWidget):
                self.GetPolyData(self._pd)
                pts = self._pd.GetPoints()
                if pts:
                    self._b = pts.GetBounds()

            # set other widgets bounds/transform
            for ax in list(self.fig.getp('axes').values()):
                if ax == self.ax:
                    continue
                if getattr(ax, '_iw', None) is not None:
                    if all(isinstance(_, vtkBoxWidget) for _ in (self, ax._iw)):
                        ax._iw._t = self._t
                        ax._iw.SetTransform(self._t)
                        ax._iw.InvokeEvent('InteractionEvent')
                    elif all(isinstance(_, vtkImplicitPlaneWidget) for _ in (self, ax._iw)):
                        ax._iw._pd = self._pd
                        ax._iw._b = self._b
                        ax._iw.PlaceWidget(ax._iw._b)
                        ax._iw.InvokeEvent('InteractionEvent')

        def __str__(self):
            return '\n'.join(['{}:{}'.format(k, v) for (k, v) in self.__dict__.items()])

    return _vtkInteractiveWidget(plane, **kwargs)


@jit
def _set_points_vectors_2d(x, y, z, u, v, w, points, vectors):
    nx, ny = u.shape
    ind = 0
    for j in range(ny):
        for i in range(nx):
            points.SetPoint(ind, x[i, j], y[i, j], z[i, j])
            vectors.SetTuple3(ind, u[i, j], v[i, j], w[i, j])
            ind += 1


@jit
def _set_points_vectors_3d(x, y, z, u, v, w, points, vectors):
    nx, ny, nz = u.shape
    ind = 0
    for k in range(nz):
        for j in range(ny):
            for i in range(nx):
                points.SetPoint(ind, x[i, j, k], y[i, j, k], z[i, j, k])
                vectors.SetTuple3(ind, u[i, j, k], v[i, j, k], w[i, j, k])
                ind += 1


@jit
def _set_points_scalars_2d(x, y, z, v, points, scalars):
    nx, ny = v.shape
    ind = 0
    for j in range(ny):
        for i in range(nx):
            points.SetPoint(ind, x[i, j], y[i, j], z[i, j])
            scalars.SetValue(ind, v[i, j])
            ind += 1


@jit
def _set_points_scalars_3d(x, y, z, v, points, scalars):
    nx, ny, nz = v.shape
    ind = 0
    for k in range(nz):
        for j in range(ny):
            for i in range(nx):
                points.SetPoint(ind, x[i, j, k], y[i, j, k], z[i, j, k])
                scalars.SetValue(ind, v[i, j, k])
                ind += 1


@jit
def _set_points_scalars_pseudoc_3d(x, y, z, v, c, points, scalars, pseudoc):
    nx, ny, nz = v.shape
    ind = 0
    for k in range(nz):
        for j in range(ny):
            for i in range(nx):
                points.SetPoint(ind, x[i, j, k], y[i, j, k], z[i, j, k])
                scalars.SetValue(ind, v[i, j, k])
                pseudoc.SetValue(ind, c[i, j, k])
                ind += 1


@jit
def _set_norm_3d(x, y, z, u, v, w, scalars):
    nx, ny, nz = v.shape
    ind = 0
    for k in range(nz - 1):
        for j in range(ny - 1):
            for i in range(nx - 1):
                scalars.SetValue(ind, np.sqrt(u[i, j, k]**2 + v[i, j, k]**2 + w[i, j, k]**2))
                ind += 1


class VTKBackend(BaseClass):

    def __init__(self):
        super().__init__()
        self._init()

    def _invertc(self, color):
        'invert rgb colors, pass if str or anything else'
        try:
            if len(color) == 3:
                return tuple(1 - _ for _ in color)
        except:
            pass

    def _init(self, *args, **kwargs):
        'perform initialization that is special for this backend'

        if 'tk' in VTK_BACKEND.lower():
            self._master = tkinter.Tk()
            self._master.withdraw()
        else:
            self._master = QtGui.QApplication([])

        self.figure(self.getp('curfig'))

        # conversion tables for format strings:
        self._markers = {
            '': None,   # no marker
            '.': None,  # dot
            'o': None,  # circle
            'x': None,  # cross
            '+': None,  # plus sign
            '*': None,  # asterisk
            's': None,  # square
            'd': None,  # diamond
            '^': None,  # triangle (up)
            'v': None,  # triangle (down)
            '<': None,  # triangle (left)
            '>': None,  # triangle (right)
            'p': None,  # pentagram
            'h': None,  # hexagram
        }

        self._arrow_types = {
            # tuple: (type,rotation)
            '': (9, 0),   # arrow
            '.': (0, 0),   # no marker
            'o': (7, 0),   # circle
            '+': (3, 0),   # plus
            'x': (3, 45),  # x-mark
            '*': (3, 0),   # star --> plus
            's': (6, 0),   # square
            'd': (8, 0),   # diamond
            'v': (5, 180),  # triangle (down)
            '^': (5, 0),   # triangle (up)
            '<': (5, 90),  # triangle (left)
            '>': (5, 270),  # triangle (right)
            'p': (6, 0),   # pentagram --> square
            'h': (6, 0),   # hexagram --> square
        }

        self._colors = {
            '': None,            # no color --> blue
            'r': (1, 0, 0),      # red
            'g': (0, 1, 0),      # green
            'b': (0, 0, 1),      # blue
            'c': (0, 1, 1),      # cyan
            'm': (1, 0, 1),      # magenta
            'y': (1, 1, 0),      # yellow
            'k': (0, 0, 0),      # black
            'w': (1, 1, 1),      # white
            'db': (.1, .2, .3),  # paraview dark blue
            'lb': (.2, .3, .4),  # paraview light blue
            'lg': (.8, .8, .8),  # light gray
            'dg': (.9, .9, .9)   # light gray
        }

        self._colors = dict({'_' + k: self._invertc(v) for (k, v) in self._colors.items()}, **self._colors)

        self._line_styles = {
            '': None,    # no line
            '-': None,   # solid line
            ':': None,   # dotted line
            '-.': None,  # dash-dot line
            '--': None,  # dashed line
        }

        # convert table for colorbar location:
        self._colorbar_locations = {
            'North': None,
            'South': None,
            'East': None,
            'West': None,
            'NorthOutside': None,
            'SouthOutside': None,
            'EastOutside': None,
            'WestOutside': None,
        }

        if DEBUG:
            print('<backend standard variables>')
            for disp in 'self._markers self._colors self._line_styles'.split():
                print(disp, eval(disp))

    def _get_color(self, color, default=None):
        if not (isinstance(color, (tuple, list)) and len(color) == 3):
            color = self._colors.get(color, default)
            if color is None:
                color = default
        return color

    def _set_scale(self, ax):
        'set linear or logarithmic (base 10) axis scale'
        _print('<scales>')

        scale = ax.getp('scale')
        if scale == 'loglog':
            # use logarithmic scale on both x- and y-axis
            pass
        elif scale == 'logx':
            # use logarithmic scale on x-axis and linear scale on y-axis
            pass
        elif scale == 'logy':
            # use linear scale on x-axis and logarithmic scale on y-axis
            pass
        elif scale == 'linear':
            # use linear scale on both x- and y-axis
            pass

    def _set_labels(self, ax):
        'add text labels for x-, y-, and z-axis'
        xlabel, ylabel, zlabel = ax.getp('xlabel'), ax.getp('ylabel'), ax.getp('zlabel')
        if (xlabel or ylabel or zlabel):
            _print('<labels>')
        if xlabel:
            # add a text label on x-axis
            pass
        if ylabel:
            # add a text label on y-axis
            pass
        if zlabel:
            # add a text label on z-axis
            pass

    def _set_title(self, ax):
        'add a title at the top of the axis'
        # title = self._fix_latex(ax.getp('title'))
        title = ax.getp('title')
        if title:
            _print('<title>')
            tprop = vtkTextProperty()
            tprop.BoldOff()
            tprop.SetFontSize(int(1.25 * ax.getp('fontsize')))
            tprop.SetColor(ax.getp('fgcolor'))
            tprop.SetFontFamilyToArial()
            tprop.SetVerticalJustificationToTop()
            tprop.SetJustificationToCentered()
            tmapper = vtkTextMapper()
            tmapper.SetInput(title)
            tmapper.SetTextProperty(tprop)
            tactor = vtkActor2D()
            tactor.SetMapper(tmapper)
            self._set_coord_in_system(tactor.GetPositionCoordinate(), (.5, .95), 'VTK_NORMALIZED_VIEWPORT')
            ax._renderer.AddActor(tactor)

    def _set_limits(self, ax):
        'set axis limits in x, y, and z direction'
        _print('<axis limits>')

        mode = ax.getp('mode')
        if mode == 'auto':
            # let plotting package set 'nice' axis limits in the x, y,
            # and z direction. If this is not automated in the plotting
            # package, one can use the following limits:
            xmin, xmax, ymin, ymax, zmin, zmax = ax.get_limits()
        elif mode == 'manual':
            # (some) axis limits are frozen
            xmin, xmax = ax.getp('xmin'), ax.getp('xmax')
            if xmin is not None and xmax is not None:
                # set x-axis limits
                pass
            else:
                # let plotting package set x-axis limits or use
                xmin, xmax = ax.getp('xlim')

            ymin, ymax = ax.getp('ymin'), ax.getp('ymax')
            if ymin is not None and ymax is not None:
                # set y-axis limits
                pass
            else:
                # let plotting package set y-axis limits or use
                ymin, ymax = ax.getp('ylim')

            zmin, zmax = ax.getp('zmin'), ax.getp('zmax')
            if zmin is not None and zmax is not None:
                # set z-axis limits
                pass
            else:
                # let plotting package set z-axis limits or use
                zmin, zmax = ax.getp('zlim')
        elif mode == 'tight':
            # set the limits on the axis to the range of the data. If
            # this is not automated in the plotting package, one can
            # use the following limits:
            xmin, xmax, ymin, ymax, zmin, zmax = ax.get_limits()
        elif mode == 'fill':
            # not sure about this
            xmin, xmax, ymin, ymax, zmin, zmax = ax.get_limits()

        elif mode == 'zerocenter':
            # not sure about this
            xmin, xmax, ymin, ymax, zmin, zmax = ax.get_limits()
            xmin, ymin, zmin = -xmax, -ymax, -zmax

        limits = [xmin, xmax, ymin, ymax, zmin, zmax]
        ax._limits = (xmin, xmax, ymin, ymax, zmin, zmax)

    def _set_position(self, ax):
        'set axes position'
        rect = ax.getp('viewport')
        if rect:
            # axes position is defined. In Matlab rect is defined as [left,bottom,width,height], where the four parameters are location values between 0 and 1 ((0,0) is the lower-left corner and (1,1) is the upper-right corner).
            # NOTE: This can be different in the plotting package.
            pass

    def _set_daspect(self, ax):
        'set data aspect ratio'
        dar = ax.getp('daspect')  # dar is a list (len(dar) is 3).
        # the axis limits are stored as ax._limits
        lim = list(ax._limits)
        lim[0] /= dar[0]; lim[1] /= dar[0]
        lim[2] /= dar[1]; lim[3] /= dar[1]
        lim[4] /= dar[2]; lim[5] /= dar[2]
        ax._scaled_limits = tuple(lim)

    def _set_axis_method(self, ax):
        method = ax.getp('method')
        if method == 'equal':
            # tick mark increments on the x-, y-, and z-axis should be equal in size.
            pass
        elif method == 'image':
            # same effect as axis('equal') and axis('tight')
            pass
        elif method == 'square':
            # make the axis box square in size
            pass
        elif method == 'normal':
            # full size axis box
            pass
        elif method == 'vis3d':
            # freeze data aspect ratio when rotating 3D objects
            pass

    def _set_coordinate_system(self, ax):
        'use either the default Cartesian coordinate system or a matrix coordinate system'

        direction = ax.getp('direction')
        if direction == 'ij':
            # Use matrix coordinates. The origin of the coordinate system is the upper-left corner. The i-axis should be vertical and numbered from top to bottom, while the j-axis should be horizontal and numbered from left to right
            # o---j--->
            # |
            # i
            # |
            # v
            pass
        elif direction == 'xy':
            # use the default Cartesian axes form. The origin is at the lower-left corner. The x-axis is horizontal and numbered from left to right, while the y-axis is vertical and numbered from bottom to top
            # ^
            # |
            # y
            # |
            # o---x--->
            pass

    def _set_box(self, ax):
        'turn box around axes boundary on or off, for vtk we use it to plot the axes'
        # see cubeAxes.py
        if ax.getp('box'):
            _print('<box>')
            normals = vtkPolyDataNormals()
            normals.SetInputConnection(ax._apd.GetOutputPort())
            outline = vtkOutlineFilter()
            outline.SetInputConnection(normals.GetOutputPort())
            mapOutline = vtkPolyDataMapper()
            mapOutline.SetInputConnection(outline.GetOutputPort())
            outlineActor = vtkActor()
            outlineActor.SetMapper(mapOutline)
            outlineActor.GetProperty().SetColor(0, 0, 0)
            tprop = vtkTextProperty()
            tprop.SetColor(1, 1, 1)
            tprop.ShadowOn()
            axes = vtkCubeAxesActor2D()
            axes.SetInputConnection(normals.GetOutputPort())
            axes.SetCamera(ax._renderer.GetActiveCamera())
            axes.SetLabelFormat('%6.4g')
            # axes.SetFlyModeToOuterEdges()
            axes.SetFlyModeToClosestTriad()
            axes.SetFontFactor(.9)
            axes.SetAxisTitleTextProperty(tprop)
            axes.SetAxisLabelTextProperty(tprop)

            ax._renderer.AddViewProp(outlineActor)
            ax._renderer.AddViewProp(axes)
        else:
            pass

    def _set_grid(self, ax):
        'turn grid lines on or off, for vtk we use this to plot the grid points'
        if ax.getp('grid'):
            _print('<grid>')
            # turn grid lines on
            geom = vtkStructuredGridGeometryFilter()
            geom.SetInputConnection(self.sgrid.GetOutputPort())
            mapper = vtkPolyDataMapper()
            mapper.SetInputConnection(geom.GetOutputPort())
            mapper.ScalarVisibilityOff()
            # mapper.SetLookupTable(self._ax._colormap)  # why use a colormap on grid points ?
            actor = vtkActor()
            actor.SetMapper(mapper)
            actor.GetProperty().SetColor(*ax.getp('axiscolor'))
            ax._renderer.AddActor(actor)
            ax._apd.AddInputConnection(geom.GetOutputPort())
        else:
            pass

    def _set_hidden_line_removal(self, ax):
        'turn on/off hidden line removal for meshes'
        if ax.getp('hidden'):
            _print('<hidden line removal>')
            # turn hidden line removal on
            pass
        else:
            pass

    @staticmethod
    def _set_coord_in_system(vtkcoord, coord, system='VTK_WORLD'):
        def key_from_val(val, d=VTK_COORD_SYS):
            'reverse lookup in a dictionary (given a value, returns a key)'
            try:
                return list(d.keys())[list(d.values()).index(val)]
            except:
                return
        _ = key_from_val(system)
        if _ is not None:
            vtkcoord.SetCoordinateSystem(_)
        assert _ == vtkcoord.GetCoordinateSystem()
        vtkcoord.SetValue(coord if len(coord) == 3 else (*coord, 0))

    @staticmethod
    def _get_caxis(ax, obj, auto=True, noi=None, poc='GetPointData'):
        '''
        get color axis from ax, center the range if caxismode == zerocenter
        poc: point or cell data
        noi: name or idx
        '''
        cax = ax._caxis
        if cax is None:
            obj.Update(); opt = obj.GetOutput()
            '''
            vtkDataSet.GetScalarRange()
            If the data has both point data and cell data, it returns the (min/max) range of combined point and cell data
            If there are no point or cell scalars the method will return (0,1)
            '''
            cax = opt.GetScalarRange() if noi is None else getattr(opt, poc)().GetArray(noi).GetRange()
        if ax.getp('caxismode') == 'zerocenter':
            cax = (-max(cax), max(cax))
        return cax

    def _set_colorbar(self, ax):
        'add a colorbar to the axis'
        cbar = ax.getp('colorbar')
        if cbar.getp('visible'):
            _print('<colorbar>')
            cbar_title = cbar.getp('cbtitle')
            # TODO: position the scalarbar actor according to cbar_location
            # The initial scalar bar size is (.05 x .8) of the viewport size (doc vtk)
            cbar_location = self._colorbar_locations[cbar.getp('cblocation')]
            scalarBar = vtkScalarBarActor()
            scalarBar.SetLookupTable(ax._colormap)
            scalarBar.SetTitle(cbar.getp('cbtitle'))
            scalarBar.SetOrientationToHorizontal()
            self._set_coord_in_system(scalarBar.GetPositionCoordinate(), (.25, .05), 'VTK_NORMALIZED_VIEWPORT')
            self._set_coord_in_system(scalarBar.GetPosition2Coordinate(), (.5, .1), 'VTK_NORMALIZED_VIEWPORT')
            # scalarBar.SetTitleRatio(.8 * scalarBar.GetTitleRatio())
            if True:
                scalarBar.UnconstrainedFontSizeOn()
                scalarBar.GetLabelTextProperty().SetFontSize(int(1.1 * scalarBar.GetLabelTextProperty().GetFontSize()))
            ax._renderer.AddActor(scalarBar)

    @staticmethod
    def _set_caxis(ax):
        'set the color axis scale'
        _print('<caxis>')

        if ax.getp('caxismode') == 'manual' or ax.getp('caxismode') == 'zerocenter':
            cmin, cmax = ax.getp('caxis')
            # NOTE: cmin and cmax might be None:
            if cmin is None or cmax is None:
                cmin, cmax = [0, 1]
            # set color axis scaling according to cmin and cmax
            ax._caxis = (cmin, cmax)
        else:
            # use autoranging for color axis scale
            ax._caxis = None

    def _set_colormap(self, ax):
        'set the colormap'
        _print('<colormap>')

        cmap = ax.getp('colormap')
        # cmap is plotting package dependent
        if cmap is None:
            cmap = self.vtk_lut_from_mpl('viridis')  # use default colormap
        elif not isinstance(cmap, vtkLookupTable):
            cmap = self.vtk_lut_from_mpl(cmap)  # construct lut from the given cmap (could be matplotlib, ...)
        ax._colormap = cmap

    def _set_view(self, ax):
        'set viewpoint specification'
        _print('<view>')

        def print_cam(camera, msg):
            names = ('pos', 'viewup', 'proj_dir', 'focalpoint', 'viewangle', 'plane_norm', 'wincenter', 'viewshear', 'orientation', 'orientationWXYZ', 'roll')
            props = [getattr(camera, _)() for _ in ('GetPosition', 'GetViewUp', 'GetDirectionOfProjection', 'GetFocalPoint', 'GetViewAngle', 'GetViewPlaneNormal', 'GetWindowCenter', 'GetViewShear', 'GetOrientation', 'GetOrientationWXYZ', 'GetRoll')]
            print(' '.join([str(hex(id(camera))), msg, '.' * 25]))
            for name, prop in zip(names, props):
                print(name, prop, end=' ')
            print()

        # unit axes
        if ax.getp('unit'):
            axes = vtkAxesActor()
            xmin, xmax, ymin, ymax, zmin, zmax = ax._scaled_limits
            xspan, yspan, zspan = .5 * abs(xmax - xmin), .5 * abs(ymax - ymin), .5 * abs(zmax - zmin)
            axes.SetTotalLength((.2 * max(xspan, yspan, zspan),) * 3)
            for _ in (axes.GetXAxisCaptionActor2D(), axes.GetYAxisCaptionActor2D(), axes.GetZAxisCaptionActor2D()):
                _.GetTextActor().SetTextScaleModeToNone()
            # axes.SetScale(.5)
            ax._renderer.AddActor(axes)

        cam = ax.getp('camera')
        view, focalpoint, position, upvector = cam.getp('view'), cam.getp('camtarget'), cam.getp('campos'), cam.getp('camup')
        camroll, viewangle = cam.getp('camroll'), cam.getp('camva')

        camera = vtkCamera()
        '''
        here we loop over all the axis of the figure: if there is an existing camera, then we share it
        therefore, it is not necessary to call _ = ez.subplot(121) <...> ez.subplot(122, _camera=_._camera)
        '''
        for axis in self.gcf().getp('axes').values():
            _ = getattr(axis, '_camera', None)
            if _ is not None:
                # update local camera with the one from cam.setp(**axis.getp('camera')._prop)
                ax.setp(camera=axis.getp('camera'))
                camera = axis._camera
                cam = ax.getp('camera')
                break

        camera.SetViewUp(upvector)
        camera.ParallelProjectionOn()
        # print_cam(camera, '1')
        if view == 2:
            camera.SetPosition(focalpoint[0], focalpoint[1], 1)  # setup a default 2D view
        elif view == 3:
            if cam.getp('cammode') == 'manual':
                if cam.getp('camproj') == 'orthographic':
                    camera.ParallelProjectionOn()
                else:
                    camera.ParallelProjectionOff()
                # print('manual', upvector, focalpoint, position)
                # for advanced camera handling:
                camera.Roll(0)
                camera.Yaw(0)
                camera.Pitch(0)
                camera.Azimuth(0)
                camera.Elevation(0)
                camera.SetPosition(position)
                camera.SetViewUp(upvector)
                camera.SetFocalPoint(focalpoint)
                # camera.Dolly(cam.getp('camdolly'))
                if viewangle is not None:
                    camera.SetViewAngle(viewangle)
                if camroll is not None:
                    camera.SetRoll(camroll)
                # print_cam(camera, '2')
            else:
                camera.SetPosition(focalpoint[0], focalpoint[1] - 1, focalpoint[2])
                az, el = cam.getp('azimuth'), cam.getp('elevation')
                if az is None or el is None:
                    # azimuth or elevation is not given. Set up a default 3D view (az=-37.5 and el=30 is the default 3D view in Matlab).
                    az = -37.5
                    el = 30
                camera.Azimuth(az)
                camera.Elevation(el)

        ax._renderer.SetActiveCamera(camera)
        ax._camera = camera
        cam.setp(camshare=camera)

        if cam.getp('cammode') == 'auto':
            ax._renderer.ResetCamera()
        else:
            # print('reset camera using', ax._scaled_limits)
            ax._renderer.ResetCamera(ax._scaled_limits)
        camera.Zoom(cam.getp('camzoom'))

        # print(hex(id(self._ax)), 'axis')
        # print(hex(id(cam)), 'camera')
        # print(hex(id(camera)), 'vtkCamera')
        # print(cam)
        # print_cam(camera, '3')
        # print(camera)
        # print('__' * 25)

    def _set_axis_props(self, ax):
        _print('<axis properties>')
        self._set_title(ax)
        self._set_scale(ax)
        self._set_limits(ax)
        self._set_position(ax)
        self._set_axis_method(ax)
        self._set_daspect(ax)
        self._set_coordinate_system(ax)
        self._set_hidden_line_removal(ax)
        self._set_colorbar(ax)
        self._set_caxis(ax)
        self._set_colormap(ax)
        self._set_view(ax)
        if ax.getp('visible'):
            self._set_labels(ax)
            self._set_box(ax)
            self._set_grid(ax)
        else:
            # turn off all axis labeling, tickmarks, and background
            pass

    def _is_inside_limits(self, data):
        'returns True if data limits is inside axis limits'
        slim = self._ax._scaled_limits
        dlim = data.GetBounds()
        for _ in range(0, len(slim), 2):
            if dlim[i] < slim[_] and not np.allclose(dlim[_], slim[_]):
                return False
        for _ in range(1, len(slim), 2):
            if dlim[_] > slim[_] and not np.allclose(dlim[_], slim[_]):
                return False
        return True

    def _cut_data(self, data, item):
        '''
        return cutted data if limits is outside (scaled) axis limits
        NOTE: slicing should be made before the call to scitools
        (when performance issue with glyphs and multiple subplots for example)
        '''
        islice = item.getp('islice')

        # data boundaries clipper
        box = vtkBox()
        box.SetBounds(self._ax._scaled_limits)

        clipper = vtkClipPolyData()
        clipper.SetInputConnection(data.GetOutputPort())
        clipper.SetClipFunction(box)
        clipper.SetValue(0)
        clipper.InsideOutOn()

        if islice:
            # see github.com/vmtk/vmtk/blob/master/vmtkScripts/vmtkmeshclipper.pys
            self._ax._iw = vtkInteractiveWidget(
                'boxwidget' if islice == 'cube' else 'implicitplanewidget',
                ax=self._ax,
                fig=self.fig,
                ic=data.GetOutputPort()
            )

            iclipper = vtkClipPolyData()
            iclipper.SetInputConnection(data.GetOutputPort())
            iclipper.SetClipFunction(self._ax._iw._p)
            iclipper.SetValue(0)
            iclipper.InsideOutOn()

            def pw_interaction(obj, event):
                # see www.python.org/dev/peps/pep-3104 for nonlocal kw
                obj._GetPlane()

            def pw_start_interaction(obj, event):
                if isinstance(obj, vtkBoxWidget):
                    obj.OutlineCursorWiresOn()
                    obj.GetHandleProperty().SetOpacity(.5)
                obj.GetOutlineProperty().SetOpacity(.5)

            def pw_end_interaction(obj, event):
                if isinstance(obj, vtkBoxWidget):
                    obj.OutlineCursorWiresOff()
                    obj.GetHandleProperty().SetOpacity(.2)
                obj.GetOutlineProperty().SetOpacity(0)
                obj._SaveWidget()

            def pw_enable(obj, event):
                nonlocal iclipper, clipper
                clipper.SetInputConnection(iclipper.GetOutputPort())
                obj._on = True
                print('on')
                pw_interaction(obj, event)
                pw_end_interaction(obj, event)

            def pw_disable(obj, event):
                nonlocal data, clipper
                obj._on = False
                print('off')
                clipper.SetInputConnection(data.GetOutputPort())
                obj._SaveWidget()

            for _ in (pw_interaction, pw_start_interaction, pw_end_interaction, pw_enable, pw_disable):
                setattr(self._ax._iw, _.__name__, _)

            self._ax._iw._AddObservers()

            pw_interaction(self._ax._iw, None)  # in order to avoid 'Please define points and/or normals!' errors

        return clipper

    def _set_shading(self, item, source, actor):
        'shading + mesh contour'
        shading = self._ax.getp('shading')
        _print('<shading>')

        if shading == 'interp':
            actor.GetProperty().SetInterpolationToGouraud()
        elif shading == 'flat':
            actor.GetProperty().SetInterpolationToFlat()
        else:
            actor.GetProperty().SetInterpolationToPhong()
            edges = vtkExtractEdges()
            edges.SetInputConnection(source.GetOutputPort())
            mapper = vtkPolyDataMapper()
            mapper.SetInputConnection(edges.GetOutputPort())
            mapper.ScalarVisibilityOff()
            mapper.SetResolveCoincidentTopologyToPolygonOffset()

            edgecolor = self._colors.get(item.getp('edgecolor'), None)
            if edgecolor is None:
                # try items linecolor property:
                edgecolor = self._colors.get(item.getp('linecolor'), None)

            if edgecolor is not None:
                mesh = vtkActor()
                mesh.SetMapper(mapper)
                mesh.GetProperty().SetColor(edgecolor)
                self._ax._renderer.AddActor(mesh)

    def _set_actor_properties(self, item, actor):
        'set line properties'
        color = self._get_color(item.getp('linecolor'), (0, 0, 1))
        prop = actor.GetProperty()
        prop.SetColor(color)
        if item.getp('linetype') == '--':
            prop.SetLineStipplePattern(65280)
        elif item.getp('linetype') == ':':
            prop.SetLineStipplePattern(0x1111)
            prop.SetLineStippleRepeatFactor(1)
        # actor.GetProperty().SetPointSize(item.getp('pointsize'))
        linewidth = item.getp('linewidth')
        if linewidth:
            prop.SetLineWidth(float(linewidth))
        if item.getp('edgevisibility'):
            prop.EdgeVisibilityOn()

    def _set_actor_material_properties(self, item, actor):
        'set material properties'
        ax = self._ax
        mat = item.getp('material')
        if mat.getp('opacity') is not None:
            actor.GetProperty().SetOpacity(mat.getp('opacity'))
        if mat.getp('ambient') is not None:
            actor.GetProperty().SetAmbient(mat.getp('ambient'))
        if ax.getp('ambientcolor') is not None:
            actor.GetProperty().SetAmbientColor(ax.getp('ambientcolor'))
        if mat.getp('diffuse') is not None:
            actor.GetProperty().SetDiffuse(mat.getp('diffuse'))
        if ax.getp('diffusecolor') is not None:
            actor.GetProperty().SetDiffuseColor(ax.getp('diffusecolor'))
        if mat.getp('specular') is not None:
            actor.GetProperty().SetSpecular(mat.getp('specular'))
        if mat.getp('specularpower') is not None:
            actor.GetProperty().SetSpecularPower(mat.getp('specularpower'))

    def _create_2D_scalar_data(self, item):
        x, y = np.squeeze(item.getp('xdata')), np.squeeze(item.getp('ydata'))
        z = np.asarray(item.getp('zdata'))  # scalar field
        try:
            c = item.getp('cdata')       # pseudocolor data
        except KeyError:
            c = z.copy()

        c = z.copy() if c is None else np.asarray(c)
        assert c.shape == z.shape

        if x.shape != z.shape and y.shape != z.shape:
            assert x.ndim == 1 and y.ndim == 1
            x, y = np.meshgrid(x, y, indexing=item.getp('indexing'))
            # FIXME: use np.ndgrid instead of np.meshgrid
        assert x.shape == z.shape and y.shape == z.shape

        # scale x, y, and z according to data aspect ratio:
        dx, dy, dz = self._ax.getp('daspect')
        x, y, z = x / dx, y / dy, z / dz

        function = item.getp('function')
        if function in ['contour', 'contourf', 'pcolor']:
            z *= 0
        if function in ['meshc', 'surfc'] and isinstance(item, Contours):
            # this item is the Contours object beneath the surface in a meshc or surfc plot.
            # we add an epsilon value else we can have 'no input data' troubles
            z *= 0
            z += self._ax._scaled_limits[4] + np.finfo(np.float32).eps

        points = vtkPoints()
        points.SetNumberOfPoints(item.getp('numberofpoints'))
        scalars = vtkFloatArray()
        scalars.SetName('vectors')
        scalars.SetNumberOfTuples(item.getp('numberofpoints'))
        scalars.SetNumberOfComponents(1)

        _set_points_scalars_2d(x, y, z, c, points, scalars)

        sgrid = vtkStructuredGrid()
        sgrid.SetDimensions(item.getp('dims'))
        sgrid.SetPoints(points)
        sgrid.GetPointData().SetScalars(scalars)

        self.sgrid = vtkAlgorithmSource(sgrid)
        return self.sgrid

    def _create_2D_vector_data(self, item):
        # grid coordinates
        x, y = np.squeeze(item.getp('xdata')), np.squeeze(item.getp('ydata'))
        z = item.getp('zdata')           # scalar field
        # vector components
        u, v = np.asarray(item.getp('udata')), np.asarray(item.getp('vdata'))
        w = item.getp('wdata')

        z = np.zeros(u.shape) if z is None else np.squeeze(z)
        w = np.zeros(u.shape) if w is None else np.asarray(w)

        # print(z, w)
        # print(u.shape, w.shape)
        # print(x.shape == u.shape, y.shape == u.shape, z.shape == u.shape, v.shape == u.shape, w.shape == u.shape)

        # scale x, y, and z according to data aspect ratio:
        dx, dy, dz = self._ax.getp('daspect')
        x, y, z = x / dx, y / dy, z / dz

        if x.shape != u.shape and y.shape != u.shape:
            assert x.ndim == 1 and y.ndim == 1
            x, y = np.meshgrid(x, y, indexing=item.getp('indexing'))
            # FIXME: use np.ndgrid instead of np.meshgrid
        assert x.shape == u.shape and y.shape == u.shape and z.shape == u.shape and v.shape == u.shape and w.shape == u.shape

        n = item.getp('numberofpoints')
        points = vtkPoints()
        points.SetNumberOfPoints(n)
        vectors = vtkFloatArray()
        vectors.SetName('vectors')
        vectors.SetNumberOfTuples(n)
        vectors.SetNumberOfComponents(3)
        vectors.SetNumberOfValues(3 * n)

        _set_points_vectors_2d(x, y, z, u, v, w, points, vectors)

        sgrid = vtkStructuredGrid()
        sgrid.SetDimensions(item.getp('dims'))
        sgrid.SetPoints(points)
        sgrid.GetPointData().SetVectors(vectors)

        self.sgrid = vtkAlgorithmSource(sgrid)
        return self.sgrid

    def _create_3D_scalar_data(self, item):
        x, y, z = np.squeeze(item.getp('xdata')), np.squeeze(item.getp('ydata')), np.squeeze(item.getp('zdata'))
        v = np.asarray(item.getp('vdata'))  # scalar data
        c = item.getp('cdata')           # pseudocolor data

        if x.shape != v.shape and y.shape != v.shape and z.shape != v.shape:
            assert x.ndim == 1 and y.ndim == 1 and z.ndim == 1
            x, y, z = np.meshgrid(x, y, z, indexing=item.getp('indexing'))
            # FIXME: use np.ndgrid instead of np.meshgrid
        assert x.shape == v.shape and y.shape == v.shape and z.shape == v.shape

        # scale x, y, and z according to data aspect ratio:
        dx, dy, dz = self._ax.getp('daspect')
        x, y, z = x / dx, y / dy, z / dz

        points = vtkPoints()
        points.SetNumberOfPoints(item.getp('numberofpoints'))
        scalars = vtkFloatArray()
        scalars.SetName('scalars')
        scalars.SetNumberOfTuples(item.getp('numberofpoints'))
        scalars.SetNumberOfComponents(1)
        if c is not None:
            pseudoc = vtkFloatArray()
            pseudoc.SetName('pseudocolor')
            pseudoc.SetNumberOfTuples(item.getp('numberofpoints'))
            pseudoc.SetNumberOfComponents(1)

        if c is not None:
            _set_points_scalars_pseudoc_3d(x, y, z, v, c, points, scalars, pseudoc)
        else:
            _set_points_scalars_3d(x, y, z, v, points, scalars)

        sgrid = vtkStructuredGrid()
        sgrid.SetDimensions(item.getp('dims'))
        sgrid.SetPoints(points)
        sgrid.GetPointData().SetScalars(scalars)

        if True:
            # public.kitware.com/pipermail/vtkusers/2004-August/026366.html
            # insert an additionnal array, but do not make it active
            sgrid.GetPointData().AddArray(pseudoc) if c is not None else None
            self.sgrid = vtkAlgorithmSource(sgrid)
        else:
            if c is not None:
                sgridc = vtkStructuredGrid()
                sgridc.SetDimensions(item.getp('dims'))
                sgridc.SetPoints(points)
                sgridc.GetPointData().SetScalars(pseudoc)

            self.sgrid = vtkAlgorithmSource([sgrid, sgridc])
        return self.sgrid

    def _create_3D_vector_data(self, item):
        # grid components
        x, y, z = np.squeeze(item.getp('xdata')), np.squeeze(item.getp('ydata')), np.squeeze(item.getp('zdata'))
        # vector components
        u, v, w = np.asarray(item.getp('udata')), np.asarray(item.getp('vdata')), np.asarray(item.getp('wdata'))

        # scale x, y, and z according to data aspect ratio:
        dx, dy, dz = self._ax.getp('daspect')
        x, y, z = x / dx, y / dy, z / dz

        if x.shape != u.shape and y.shape != u.shape and z.shape != u.shape:
            assert x.ndim == 1 and y.ndim == 1 and z.ndim == 1
            x, y, z = np.meshgrid(x, y, z, indexing=item.getp('indexing'))
            # FIXME: use np.ndgrid instead of np.meshgrid
        assert x.shape == u.shape and y.shape == u.shape and z.shape == u.shape and v.shape == u.shape and w.shape == u.shape

        n = item.getp('numberofpoints')
        points = vtkPoints()
        points.SetNumberOfPoints(n)
        vectors = vtkFloatArray()
        vectors.SetName('vectors')
        vectors.SetNumberOfTuples(n)
        vectors.SetNumberOfComponents(3)
        vectors.SetNumberOfValues(3 * n)
        nx, ny, nz = u.shape
        nc = (nx - 1) * (ny - 1) * (nz - 1)
        scalars = vtkFloatArray()
        scalars.SetName('scalars')
        scalars.SetNumberOfTuples(nc)
        scalars.SetNumberOfComponents(1)
        scalars.SetNumberOfValues(nc)

        _set_points_vectors_3d(x, y, z, u, v, w, points, vectors)

        _set_norm_3d(x, y, z, u, v, w, scalars)

        sgrid = vtkStructuredGrid()
        sgrid.SetDimensions(item.getp('dims'))
        sgrid.SetPoints(points)
        sgrid.GetPointData().SetScalars(scalars)
        sgrid.GetPointData().SetVectors(vectors)

        self.sgrid = vtkAlgorithmSource(sgrid)
        return self.sgrid

    def _create_3D_line_data(self, item):
        # TODO generate a polydata with lines see CylinderContour.py
        x, y, z = item.getp('xdata'), item.getp('ydata'), item.getp('zdata')
        if z is None:
            z = np.zeros(x.shape)

        points = vtkPoints()
        [points.InsertPoint(_, x[_], y[_], z[_]) for _ in range(len(x))]

        lines = vtkCellArray()
        lines.InsertNextCell(len(x))

        [lines.InsertCellPoint(_) for _ in range(len(x) - 1)]
        lines.InsertCellPoint(0)

        polydata = vtkPolyData()
        polydata.SetPoints(points)
        polydata.SetLines(lines)

        sgrid = vtkStructuredGrid()
        sgrid.SetDimensions(item.getp('dims'))
        sgrid.SetPoints(points)
        self.sgrid = vtkAlgorithmSource(sgrid)

        return vtkAlgorithmSource(polydata, outputType='vtkPolyData')

    def _get_linespecs(self, item):
        'Return the line marker, line color, line style, and line width of the item'
        marker = self._markers[item.getp('linemarker')]
        color = self._colors[item.getp('linecolor')]
        style = self._line_styles[item.getp('linetype')]
        width = item.getp('linewidth')
        return marker, color, style, width

    def _add_line(self, item):
        'Add a 2D or 3D curve to the scene'
        _print('<line +>')

        # get line specifications, TODO: set them in VTK
        marker, color, style, width = self._get_linespecs(item)

        line3D = self._create_3D_line_data(item)
        data = self._cut_data(line3D, item)
        mapper = vtkDataSetMapper()
        mapper.SetInputConnection(data.GetOutputPort())
        mapper.SetLookupTable(self._ax._colormap)
        mapper.SetScalarRange(self._get_caxis(self._ax, data))
        actor = vtkActor()
        actor.SetMapper(mapper)
        self._set_actor_properties(item, actor)
        self._ax._renderer.AddActor(actor)
        self._ax._apd.AddInputConnection(data.GetOutputPort())

    def _add_surface(self, item, shading='faceted'):
        _print('<surface +>')

        sgrid = self._create_2D_scalar_data(item)
        contours = item.getp('contours')
        if contours:
            # the current item is produced by meshc or surfc and we
            # should therefore add contours at the bottom:
            self._add_contours(contours, placement='bottom')

        if item.getp('wireframe'):
            # wireframe mesh (as produced by mesh or meshc)
            pass
        else:
            # colored surface (as produced by surf, surfc, or pcolor)
            # use keyword argument shading to set the color shading mode
            pass
        geom = vtkStructuredGridGeometryFilter()
        geom.SetInputConnection(sgrid.GetOutputPort())
        data = self._cut_data(geom, item)
        normals = vtkPolyDataNormals()
        normals.SetInputConnection(data.GetOutputPort())
        normals.SetFeatureAngle(45)
        mapper = vtkDataSetMapper()
        mapper.SetInputConnection(normals.GetOutputPort())
        mapper.SetLookupTable(self._ax._colormap)
        mapper.SetScalarRange(self._get_caxis(self._ax, data))
        actor = vtkActor()
        actor.SetMapper(mapper)
        if item.getp('wireframe'):
            actor.GetProperty().SetRepresentationToWireframe()
        else:
            self._set_shading(item, data, actor)

        self._set_actor_properties(item, actor)
        # self._add_legend(item, normals.GetOutput())
        self._ax._renderer.AddActor(actor)  # DEBUG !!
        self._ax._apd.AddInputConnection(normals.GetOutputPort())

    def _add_contours(self, item, placement=None):
        # The placement keyword can be either None or 'bottom'. The latter specifies that the contours should be placed at the  bottom (as in meshc or surfc)
        _print('<contours +>')
        sgrid = self._create_2D_scalar_data(item)
        geom = vtkStructuredGridGeometryFilter()
        geom.SetInputConnection(sgrid.GetOutputPort())
        data = self._cut_data(geom, item)

        filled = item.getp('filled')  # draw filled contour plot if True
        if filled:
            iso = vtkBandedPolyDataContourFilter()
            iso.SetScalarModeToValue()
            # iso.SetScalarModeToIndex()
            iso.GenerateContourEdgesOn()
        else:
            iso = vtkContourFilter()
        iso.SetInputConnection(data.GetOutputPort())

        cvector, clevels = item.getp('cvector'), item.getp('clevels')
        # _print('cvector', cvector, 'clevels', clevels)
        data.Update(); datao = data.GetOutput()
        if cvector is None:
            # the contour levels are chosen automagically
            zmin, zmax = datao.GetScalarRange()
            iso.SetNumberOfContours(clevels)
            iso.GenerateValues(clevels, zmin, zmax)
        else:
            [iso.SetValue(_, cvector[_]) for _ in range(clevels)]

        mapper = vtkPolyDataMapper()
        mapper.SetInputConnection(iso.GetOutputPort())
        cmap = self._ax._colormap
        if filled:
            cmap.SetNumberOfColors(clevels)
            cmap.Build()
        mapper.SetLookupTable(cmap)
        mapper.SetScalarRange(self._get_caxis(self._ax, data))
        if item.getp('linecolor'):  # linecolor is defined
            mapper.ScalarVisibilityOff()

        actor = vtkActor()
        actor.SetMapper(mapper)
        self._set_actor_properties(item, actor)
        # self.add_legend(item, iso.GetOutput())
        self._ax._renderer.AddActor(actor)
        self._ax._apd.AddInputConnection(data.GetOutputPort())

        fgcolor = self._get_color(self._ax.getp('fgcolor'), (0, 0, 0))
        edgecolor = self._get_color(item.getp('edgecolor'), fgcolor)

        if filled:
            # create contour edges:
            edgeMapper = vtkPolyDataMapper()
            edgeMapper.SetInputData(iso.GetContourEdgesOutput())
            edgeMapper.SetResolveCoincidentTopologyToPolygonOffset()
            edgeActor = vtkActor()
            edgeActor.SetMapper(edgeMapper)
            edgeActor.GetProperty().SetColor(edgecolor)
            self._ax._renderer.AddActor(edgeActor)

        if item.getp('clabels'):
            # add labels on the contour curves subsample the points and label them
            # print('    adding labels', 'fgcolor', fgcolor, 'edgecolor', edgecolor, 'bgcolor', self._ax.getp('bgcolor'))
            # print('    ratio', int(datao.GetNumberOfPoints() / 50))
            mask = vtkMaskPoints()
            mask.SetInputConnection(iso.GetOutputPort())
            mask.SetOnRatio(int(datao.GetNumberOfPoints() / 50))
            mask.SetMaximumNumberOfPoints(100)
            mask.RandomModeOn()

            # create labels for points - only show visible points
            visPts = vtkSelectVisiblePoints()
            visPts.SetInputConnection(mask.GetOutputPort())
            visPts.SetRenderer(self._ax._renderer)
            visPts.Update()  # needed, else data is out of date, see classvtkSelectVisiblePoints.html
            ldm = vtkLabeledDataMapper()
            ldm.SetInputData(mask.GetOutput())  # vtkLabeledDataMapper has no attribute 'SetInputConnnection'
            ldm.SetLabelFormat('%.1g')
            ldm.SetLabelModeToLabelScalars()
            tprop = ldm.GetLabelTextProperty()
            tprop.SetFontFamilyToArial()
            tprop.SetFontSize(int(.8 * self._ax.getp('fontsize')))
            tprop.SetColor(edgecolor)
            tprop.ShadowOff()
            tprop.BoldOff()
            contourLabels = vtkActor2D()
            contourLabels.SetMapper(ldm)
            self._ax._renderer.AddActor(contourLabels)

    def _add_vectors(self, item):
        _print('<vectors +>')

        # uncomment the following command if there is no support for automatic scaling of vectors in the current plotting package:
        item.scale_vectors()

        if item.getp('udata').ndim == 3:
            sgrid = self._create_3D_vector_data(item)
        else:
            sgrid = self._create_2D_vector_data(item)

        # get line specifiactions (marker='.' means no marker):
        marker, color, style, width = self._get_linespecs(item)

        # scale the vectors according to this variable (scale=0 should turn off automatic scaling):
        arrowscale = item.getp('arrowscale')
        cone_resolution = item.getp('cone_resolution')
        marker, rotation = self._arrow_types[item.getp('linemarker')]

        geom = vtkStructuredGridGeometryFilter()
        geom.SetInputConnection(sgrid.GetOutputPort())
        data = self._cut_data(geom, item)
        data.Update(); datao = data.GetOutput()
        glyph = vtkGlyph3D()

        if cone_resolution:
            # tip_radius, shaft_radius, tip_length = .1, .03, .35  # default vtk values
            tip_resolution, shaft_resolution = 2, 2
            arrow = vtkArrowSource()
            # arrow.SetTipLength(tip_length)
            # arrow.SetTipRadius(tip_radius)
            # arrow.SetShaftRadius(shaft_radius)
            arrow.SetTipResolution(cone_resolution * tip_resolution)
            arrow.SetShaftResolution(cone_resolution * shaft_resolution)

        else:
            arrow = vtkGlyphSource2D()
            arrow.SetGlyphType(marker)
            arrow.SetFilled(item.getp('filledarrows'))
            arrow.SetRotationAngle(rotation)
            if arrow.GetGlyphType() != 9:  # not an arrow
                arrow.DashOn()
                arrow.SetCenter(.75, 0, 0)
            else:
                arrow.SetCenter(.5, 0, 0)
            arrow.SetColor(self._get_color(item.getp('linecolor'), (0, 0, 0)))

        glyph.SetInputConnection(data.GetOutputPort())
        glyph.SetSourceConnection(arrow.GetOutputPort())
        glyph.SetColorModeToColorByVector()
        glyph.SetRange(datao.GetScalarRange())
        glyph.ScalingOn()
        glyph.SetScaleModeToScaleByVector()
        glyph.OrientOn()
        glyph.SetVectorModeToUseVector()
        glyph.SetScaleFactor(arrowscale)

        mapper = vtkPolyDataMapper()
        mapper.ScalarVisibilityOff()
        mapper.SetInputConnection(glyph.GetOutputPort())

        # glyph are costly in terms of rendering, use a LODActor
        actor = vtkLODActor()
        actor.SetMapper(mapper)
        self._set_shading(item, glyph, actor)
        self._set_actor_properties(item, actor)
        self._ax._renderer.AddActor(actor)
        self._ax._apd.AddInputConnection(glyph.GetOutputPort())

    def _add_streams(self, item):
        _print('<streams +>')

        if item.getp('udata').ndim == 3:
            sgrid = self._create_3D_vector_data(item)
        else:
            sgrid = self._create_2D_vector_data(item)

        # length = sgrid.GetLength()
        # max_velocity = sgrid.GetPointData().GetVectors().GetMaxNorm()
        # max_time = 35. * length / max_velocity

        dx, dy, dz = self._ax.getp('daspect')
        sx = np.ravel(item.getp('startx')) / dx
        sy = np.ravel(item.getp('starty')) / dy
        sz = np.ravel(np.zeros(sx.shape)) if item.getp('startz') is None else np.ravel(item.getp('startz')) / dz

        seeds = vtkProgrammableSource()

        def seeds_pts():
            output = seeds.GetPolyDataOutput()
            points = vtkPoints()
            verts = vtkCellArray()
            verts.InsertNextCell(item.getp('numberofstreams'))

            for _ in range(item.getp('numberofstreams')):
                verts.InsertCellPoint(points.InsertNextPoint(sx[_], sy[_], sz[_]))

            output.SetPoints(points)
            output.SetVerts(verts)

        seeds.SetExecuteMethod(seeds_pts)
        seeds.Update()

        # The starting point, or the so-called 'seed', of a streamline may be set in two different ways. Starting from global x-y-z 'position' allows you to start a single trace at a specified x-y-z coordinate. If you specify a source object, traces will be generated from each point in the source that is inside the dataset

        streamer = vtkStreamTracer()

        streamer.SetInputConnection(sgrid.GetOutputPort())
        streamer.SetSourceConnection(seeds.GetOutputPort())
        streamer.SetIntegrationDirectionToBoth()
        streamer.SetIntegratorTypeToRungeKutta45()
        streamer.SetComputeVorticity(item.getp('vorticity'))
        if item.getp('maxlen') is not None:
            streamer.SetMaximumPropagation(item.getp('maxlen'))

        data = self._cut_data(streamer, item)

        if item.getp('tubes'):
            ncirc = item.getp('n')
            radius = item.getp('radius')
            streamtube = vtkTubeFilter()
            streamtube.SetInputConnection(data.GetOutputPort())
            streamtube.SetRadius(radius)
            streamtube.SetNumberOfSides(ncirc)
            streamtube.SetVaryRadiusToVaryRadiusByVector()
            output = streamtube

        elif item.getp('ribbons'):
            width = item.getp('ribbonwidth')
            streamribbon = vtkRibbonFilter()
            streamribbon.SetInputConnection(data.GetOutputPort())
            streamribbon.VaryWidthOn()
            streamribbon.SetWidthFactor(width)
            # streamribbon.SetAngle(90)
            streamribbon.SetDefaultNormal([0, 1, 0])
            streamribbon.UseDefaultNormalOn()
            output = streamribbon

        else:
            output = data

        mapper = vtkPolyDataMapper()
        mapper.SetInputConnection(output.GetOutputPort())
        mapper.SetLookupTable(self._ax._colormap)
        if False:
            'why this ?'
            cax = self._ax._caxis
            if cax is None:
                # because of GetInput()
                mapper.Update(); cax = mapper.GetInput().GetBounds()[4:]
        mapper.SetScalarRange(self._get_caxis(self._ax, output))
        actor = vtkActor()
        actor.SetMapper(mapper)

        self._set_shading(item, output, actor)
        self._set_actor_properties(item, actor)
        # self._add_legend(item, output.GetOutputPort())
        self._ax._renderer.AddActor(actor)

        self._ax._apd.AddInputConnection(output.GetOutputPort())

    def _add_isosurface(self, item):
        _print('<isosurface +>')

        # grid components:
        # x, y, z = item.getp('xdata'), item.getp('ydata'), item.getp('zdata')
        # v = item.getp('vdata')  # volume
        # c = item.getp('cdata')  # pseudocolor data
        isovalue = item.getp('isovalue')

        sgrid = self._create_3D_scalar_data(item)

        iso = vtkContourFilter()
        iso.SetInputConnection(sgrid.GetOutputPort())
        iso.SetValue(0, isovalue)
        data = self._cut_data(iso, item)

        normals = vtkPolyDataNormals()
        normals.SetInputConnection(data.GetOutputPort())
        normals.SetFeatureAngle(45)

        mapper = vtkPolyDataMapper()
        mapper.SetInputConnection(normals.GetOutputPort())
        # mapper.SetScalarModeToUsePointFieldData()
        mapper.SetLookupTable(self._ax._colormap)
        mapper.SetScalarRange(self._get_caxis(self._ax, data))
        actor = vtkActor()
        actor.SetMapper(mapper)
        # self._set_shading(item, normals, actor)
        self._set_actor_properties(item, actor)
        self._ax._renderer.AddActor(actor)
        self._ax._apd.AddInputConnection(normals.GetOutputPort())

    def _add_slice_(self, item, contours=False):
        _print('<slice vol +>')

        sgrid = self._create_3D_scalar_data(item)

        sx, sy, sz = item.getp('slices')
        if sz.ndim == 2:
            # sx, sy, and sz defines a surface
            h = Surface(sx, sy, sz)
            sgrid2 = self._create_2D_scalar_data(h)
            geom = vtkStructuredGridGeometryFilter()
            geom.SetInputConnection(sgrid2.GetOutputPort())
            data = self._cut_data(geom, item)
            data.Update(); datao = data.GetOutput()
            implds = vtkImplicitDataSet()
            implds.SetDataSet(datao)
            implds.Modified()
            cut = vtkCutter()
            cut.SetInputConnection(sgrid.GetOutputPort())
            cut.SetCutFunction(implds)
            cut.GenerateValues(10, -2, 2)
            cut.GenerateCutScalarsOn()
            mapper = vtkPolyDataMapper()
            mapper.SetInputConnection(cut.GetOutputPort())
            mapper.SetLookupTable(self._ax._colormap)
            mapper.SetScalarRange(self._get_caxis(self._ax, data))
            actor = vtkActor()
            actor.SetMapper(mapper)
            if not contours:
                self._set_shading(item, data, actor)
            self._set_actor_properties(item, actor)
            self._ax._renderer.AddActor(actor)
            self._ax._apd.AddInputConnection(cut.GetOutputPort())
            self._ax._apd.AddInputConnection(data.GetOutputPort())
        else:
            # sx, sy, and sz is either numbers or vectors with numbers
            origins, normals = [], []
            sgrid.Update(); sgrido = sgrid.GetOutput()
            # print('sgrido', sgrido.GetNumberOfCells(), sgrido.GetNumberOfPoints())
            center = sgrido.GetCenter()
            dx, dy, dz = self._ax.getp('daspect')
            sx, sy, sz = np.ravel(sx) / dx, np.ravel(sy) / dy, np.ravel(sz) / dz
            for _ in range(len(sx)):
                normals.append([1, 0, 0])
                origins.append([sx[_], center[1], center[2]])
            for _ in range(len(sy)):
                normals.append([0, 1, 0])
                origins.append([center[0], sy[_], center[2]])
            for _ in range(len(sz)):
                normals.append([0, 0, 1])
                origins.append([center[0], center[1], sz[_]])
            for _ in range(len(normals)):
                plane = vtkPlane()
                plane.SetOrigin(origins[_])
                plane.SetNormal(normals[_])
                cut = vtkCutter()
                cut.SetInputConnection(sgrid.GetOutputPort())
                cut.SetCutFunction(plane)
                data = self._cut_data(cut, item)
                datao = data.GetOutput()
                # print('datao', datao.GetNumberOfCells(), datao.GetNumberOfPoints())
                mapper = vtkPolyDataMapper()
                if contours:
                    iso = vtkContourFilter()
                    iso.SetInputConnection(data.GetOutputPort())
                    cvector = item.getp('cvector')
                    if cvector is not None:
                        [iso.SetValue(_, cvector[_]) for _ in range(len(cvector))]
                    else:
                        zmin, zmax = datao.GetScalarRange()
                        iso.GenerateValues(item.getp('clevels'), zmin, zmax)
                    mapper.SetInputConnection(iso.GetOutputPort())
                else:
                    mapper.SetInputConnection(data.GetOutputPort())
                mapper.SetLookupTable(self._ax._colormap)
                mapper.SetScalarRange(self._get_caxis(self._ax, sgrid))
                actor = vtkActor()
                actor.SetMapper(mapper)
                if not contours:
                    self._set_shading(item, data, actor)
                self._set_actor_properties(item, actor)
                self._ax._renderer.AddActor(actor)
                self._ax._apd.AddInputConnection(cut.GetOutputPort())

    def _add_contourslice(self, item):
        _print('<contour slice planes +>')

        self._add_slice_(item, contours=True)

    def _setImage(self, img, color, sz):
        'helper for setting texture of a vtkButtonWidget'
        img.SetDimensions(sz, sz, 1)
        img.AllocateScalars(VTK_UNSIGNED_CHAR, 3)
        nx, ny, nz = img.GetDimensions()
        for z in range(nz):
            for y in range(ny):
                for x in range(nx):
                    [img.SetScalarComponentFromFloat(x, y, z, _, val) for _, val in enumerate(color)]

    def _setButtonWidget(self, widget, rep, on, off, sz=6):
        'configure the vtkButtonWidget, texture, state, ...'
        self._setImage(on, (0, 150, 0), sz)
        self._setImage(off, [256 * _ for _ in self._ax._renderer.GetBackground()], sz)
        rep.SetNumberOfStates(2)
        rep.SetButtonTexture(1, on)
        rep.SetButtonTexture(0, off)
        # rep.PlaceWidget(bds) # optional, position the widget, we have to use displayCoordinates !
        widget.SetRepresentation(rep)
        self._setWidgetActive(widget)

    def _setWidgetActive(self, widget):
        widget.SetInteractor(self._g.iren)
        widget.SetCurrentRenderer(self._ax._renderer)
        widget.CreateDefaultRepresentation()  # needed in order to remove the callback iren stuff ??
        widget.On()

    def _setSliderWidget(self, widget, rep, minval, maxval, val, p1, p2, ttl):
        if False:
            c1, c2 = rep.GetPoint1Coordinate(), rep.GetPoint2Coordinate()
            for c, p in [(c1, p1), (c2, p2)]:
                # before this call, c is (-1., 0., 0.) in world coordinates
                c.SetCoordinateSystemToNormalizedViewport()
                c.SetValue(p)
                _print('coord', c.GetValue(), 'viewport', c.GetViewport(), VTK_COORD_SYS[c.GetCoordinateSystem()])
                _print('(w, h)', (self._g.width, self._g.height), '(x, y)', c.GetComputedDisplayValue(self._ax._renderer))
                # print('..')
                # [_print(_.GetCoordinateSystem(), getattr(_, 'GetComputedValue')(_.GetViewport())) for _ in (c1, c2)]
                # print('--')
        self._set_coord_in_system(rep.GetPoint1Coordinate(), p1, system='VTK_NORMALIZED_DISPLAY')  # VTK_NORMALIZED_DISPLAY
        self._set_coord_in_system(rep.GetPoint2Coordinate(), p2, system='VTK_NORMALIZED_DISPLAY')  # VTK_NORMALIZED_VIEWPORT
        rep.SetMinimumValue(.95 * minval)
        rep.SetMaximumValue(1.05 * maxval)
        rep.SetValue(val)
        # cannot change the FontSize so easily, the trick is to set the Height
        # vtkusers.public.kitware.narkive.com/zysDddSG/vtkscalarbaractor-broken
        rep.SetTitleHeight(.6 * rep.GetTitleHeight())
        rep.SetLabelHeight(.6 * rep.GetLabelHeight())
        rep.SetTitleText(ttl)
        widget.SetRepresentation(rep)
        widget.SetAnimationModeToJump()
        # widget.SetAnimationModeToAnimate(); widget.SetNumberOfAnimationSteps(10)
        self._setWidgetActive(widget)

    def _add_curvature(self, item):
        _print('<curvature +>')
        v, curvtype = item.getp('vdata'), item.getp('curvtype')

        key = 'Gauss_Curvature'
        ctype = str(curvtype).lower()
        if curvtype is not None:
            key = 'Gauss_Curvature' if 'gauss' in ctype else 'Mean_Curvature' if 'mean' in ctype else 'Maximum_Curvature' if 'max' in ctype else 'Minimum_Curvature' if 'min' in ctype else key

        c_dict = dict(Gauss_Curvature=0, Mean_Curvature=1, Maximum_Curvature=2, Minimum_Curvature=3)

        sgrid = self._create_3D_scalar_data(item)

        threshold = vtkThreshold()
        threshold.SetInputConnection(sgrid.GetOutputPort())
        threshold.ThresholdBetween(v.min(), v.max())
        threshold.SetAllScalars(int(item.getp('allscalars')))

        iso = vtkMarchingContourFilter()
        iso.SetInputConnection(threshold.GetOutputPort())
        iso.SetValue(0, .5)

        '''
        vtkStructuredGridGeometryFilter
        all 0D, 1D, and 2D cells are extracted. All 2D faces that are used by only one 3D cell (i.e., boundary faces) are extracted
        '''
        # surface = vtkStructuredGridGeometryFilter()
        # surface.SetInputConnection(sgrid.GetOutputPort())
        # surface.UseStripsOn()  # No points/cells to operate on

        tris = False
        if tris:
            trifilter = vtkTriangleFilter()
            trifilter.SetInputConnection(iso.GetOutputPort())

        clean = True
        if clean:
            cleaner = vtkCleanPolyData()
            cleaner.SetInputConnection(trifilter.GetOutputPort() if tris else iso.GetOutputPort())
            # cleaner.SetTolerance(0)

        smooth = True
        if smooth:
            smoother = vtkSmoothPolyDataFilter()
            smoother.SetInputConnection(cleaner.GetOutputPort() if clean else iso.GetOutputPort())
            smoother.SetNumberOfIterations(500)

        data = self._cut_data(smoother if smooth else cleaner if clean else trifilter if tris else iso, item)

        curv = vtk.vtkCurvatures()
        curv.SetInputConnection(data.GetOutputPort())
        # [curv.SetCurvatureType(_) for _ in c_dict.values()] # all array in output
        curv.SetCurvatureType(c_dict[key])  # active array
        curv.InvertMeanCurvatureOn()

        mapper = vtkPolyDataMapper()
        mapper.SetInputConnection(curv.GetOutputPort())

        mapper.SetScalarModeToUsePointFieldData()
        mapper.SelectColorArray(key)
        mapper.SetLookupTable(self._ax._colormap)
        mapper.SetScalarRange(self._get_caxis(self._ax, curv, noi=key))

        actor = vtkActor()
        actor.SetMapper(mapper)

        self._set_actor_properties(item, actor)
        self._ax._renderer.AddActor(actor)
        self._ax._apd.AddInputConnection(curv.GetOutputPort())

        ###############
        # INTERACTIVE #
        ###############

        curvSlider, curvRep = vtkSliderWidget(), vtkSliderRepresentation2D()
        colrSlider, colrRep = vtkSliderWidget(), vtkSliderRepresentation2D()

        self._setSliderWidget(curvSlider, curvRep, v.min(), v.max(), .5 * (v.min() + v.max()), (.01, .75), (.3, .75), '[R] curvature isovalue')
        self._setSliderWidget(colrSlider, colrRep, 0, 2, 1, (.01, .65), (.3, .65), '[R] caxis')

        # FIXME: we have to make iren aware of the sliders, this is ugly, but it works
        # def fix(o, e):
        #     nonlocal curvSlider, colrSlider, curvRep, colrRep
        self._g.iren.AddObserver('EnterEvent', lambda o, e, w=(curvSlider, colrSlider, curvRep, colrRep): None)

        def cb_curv_cont(o, e):
            nonlocal iso, curv, data
            iso.SetValue(0, o.GetRepresentation().GetValue())
            if False:
                writer = vtkXMLPolyDataWriter()
                writer.SetFileName('_add_curvature_data.vtp')
                writer.SetInputConnection(data.GetOutputPort())
                writer.Write()
                writer.SetFileName('_add_curvature_curv.vtp')
                writer.SetInputConnection(curv.GetOutputPort())
                writer.Write()
                writer.SetFileName('_add_curvature_iso.vtp')
                writer.SetInputConnection(iso.GetOutputPort())
                writer.Write()
        curvSlider.AddObserver('EndInteractionEvent', cb_curv_cont)

        def cb_color(o, e):
            nonlocal self, mapper, key, curv
            val = abs(o.GetRepresentation().GetValue())
            self._ax.setp(caxis=(-val, val))
            self._set_caxis(self._ax)
            mapper.SetScalarRange(self._get_caxis(self._ax, curv, noi=key))
        colrSlider.AddObserver('EndInteractionEvent', cb_color)

        [_.InvokeEvent('EndInteractionEvent') for _ in (curvSlider, colrSlider)]

        curvSlider.Off(); curvSlider.On()
        colrSlider.Off(); colrSlider.On()

    def _add_threshold(self, item):
        _print('<threshold +>')

        v, pseudocolor = item.getp('vdata'), item.getp('cdata') is not None

        sgrid = self._create_3D_scalar_data(item)

        threshold = vtkThreshold()
        threshold.SetInputConnection(sgrid.GetOutputPort())
        threshold.SetAllScalars(int(item.getp('allscalars')))  # all points of the cell have to satisfy the criterion
        threshold.ThresholdBetween(v.min(), v.max())

        surface = vtkDataSetSurfaceFilter()
        surface.SetInputConnection(threshold.GetOutputPort())

        data = self._cut_data(surface, item)

        'failing because of the inherent regularity of vtkImageData (rectilinearGrid ?)'
        if False:
            img = vtkImageData()
            sgrid.Update(); sgrido = sgrid.GetOutput()
            v = sgrido.GetPointData().GetScalars('scalars')
            if pseudocolor:
                c = sgrido.GetPointData().GetScalars('pseudocolor')

            if True:
                img.SetDimensions(sgrido.GetDimensions())
                img.GetPointData().SetScalars(v)
                if pseudocolor:
                    img.GetPointData().AddArray(c)
            else:
                img.AllocateScalars(VTK_DOUBLE, 2 if pseudocolor else 1)
                nx, ny, nz = img.GetDimensions()
                ind = 0
                for x in range(nx):
                    for y in range(ny):
                        for z in range(nz):
                            img.SetScalarComponentFromDouble(x, y, z, 0, v.GetComponent(ind, 0))
                            if pseudocolor:
                                img.SetScalarComponentFromDouble(x, y, z, 1, c.GetComponent(ind, 0))
                            ind += 1
            img_source = vtkAlgorithmSource(img, 'vtkImageData')

            iso = vtkMarchingCubes()
            iso.SetInputConnection(img_source.GetOutputPort())
        else:
            iso = vtkMarchingContourFilter()
            iso.SetInputConnection(threshold.GetOutputPort())

        mapper = vtkPolyDataMapper()
        mapper.SetInputConnection(data.GetOutputPort())
        mapper.SetScalarModeToUsePointFieldData()
        mapper.SelectColorArray('pseudocolor' if pseudocolor else 'scalars')
        mapper.SetLookupTable(self._ax._colormap)
        mapper.SetScalarRange(self._get_caxis(self._ax, sgrid, noi='pseudocolor' if pseudocolor else 'scalars'))

        actor = vtkActor()
        actor.SetMapper(mapper)

        self._set_actor_properties(item, actor)
        self._ax._renderer.AddActor(actor)
        self._ax._apd.AddInputConnection(data.GetOutputPort())

        ###############
        # INTERACTIVE #
        ###############

        miniSlider, miniRep = vtkSliderWidget(), vtkSliderRepresentation2D()
        maxiSlider, maxiRep = vtkSliderWidget(), vtkSliderRepresentation2D()
        contSlider, contRep = vtkSliderWidget(), vtkSliderRepresentation2D()
        colrSlider, colrRep = vtkSliderWidget(), vtkSliderRepresentation2D()

        span = abs(v.max()) - abs(v.min())
        self._setSliderWidget(maxiSlider, maxiRep, v.min(), v.max(), v.max(), (.01, .95), (.3, .95), '[L] upperbound')
        self._setSliderWidget(miniSlider, miniRep, v.min(), v.max(), v.min() + .5 * span, (.01, .85), (.3, .85), '[L] lowerbound')
        self._setSliderWidget(colrSlider, colrRep, 0, 2, 1, (.01, .55), (.3, .55), '[L] caxis')
        self._setSliderWidget(contSlider, contRep, v.min(), v.max(), v.min() + .5 * span, (.01, .45), (.3, .45), '[L] contour isovalue')

        button, buttonRep, on, off = vtkButtonWidget(), vtkTexturedButtonRepresentation2D(), vtkImageData(), vtkImageData()
        self._setButtonWidget(button, buttonRep, on, off)

        # FIXME: we have to make iren aware of the sliders (no reference, object is deleted by vtk ?)
        self._g.iren.AddObserver('EnterEvent', lambda o, e, w=(miniSlider, maxiSlider, contSlider, colrSlider, button): None)

        def cb_slider(o, e):
            nonlocal threshold, miniRep, maxiRep, miniSlider, maxiSlider
            mini, maxi = miniRep.GetValue(), maxiRep.GetValue()
            minbound, maxbound = min(mini, maxi), max(mini, maxi)
            if o is miniSlider:
                miniRep.SetValue(minbound)
                threshold.ThresholdBetween(minbound, maxi)
            elif o is maxiSlider:
                maxiRep.SetValue(maxbound)
                threshold.ThresholdBetween(mini, maxbound)
        miniSlider.AddObserver('EndInteractionEvent', cb_slider)
        maxiSlider.AddObserver('EndInteractionEvent', cb_slider)

        def cb_color(o, e):
            nonlocal self, sgrid, pseudocolor, mapper
            val = abs(o.GetRepresentation().GetValue())
            self._ax.setp(caxis=(-val, val))
            self._set_caxis(self._ax)
            mapper.SetScalarRange(self._get_caxis(self._ax, sgrid, noi='pseudocolor' if pseudocolor else 'scalars'))
        colrSlider.AddObserver('EndInteractionEvent', cb_color)

        def cb_thres_cont(o, e):
            nonlocal iso
            iso.SetValue(0, o.GetRepresentation().GetValue())
        contSlider.AddObserver('EndInteractionEvent', cb_thres_cont)

        def cb_button(o, e):
            nonlocal iso, mapper, contSlider, contRep, data
            state = o.GetRepresentation().GetState()
            iso.SetValue(0, contRep.GetValue())
            contSlider.SetEnabled(state)
            mapper.SetInputConnection(iso.GetOutputPort() if state > 0 else data.GetOutputPort())
        button.AddObserver('StateChangedEvent', cb_button)

        [_.InvokeEvent('EndInteractionEvent') for _ in (miniSlider, maxiSlider)]
        button.InvokeEvent('StateChangedEvent')

    def _find_poked(self, event):
        'get the vtk[Tk,Qt]RenderWindowInteractor widget and renderer on which the event has been triggered'
        # print(dir(event))
        # for _ in dir(event):
        #     try:
        #         print(_, getattr(event, _)())
        #     except:
        #         pass
        # print(vars(event))
        fig, ax = None, None

        for fignum, _ in list(self._figs.items()):
            # compare event and find the figure
            if event and event.widget is _._g.vtkWidget:
                fig = self.figure(fignum)  # set curfig to this figure
                break

        # to use self._g, we have to have access to the poked figures
        if all(isinstance(_, int) for _ in (event.x, event.y)):
            target = fig._g.iren.FindPokedRenderer(event.x, fig._g.renwin.GetSize()[1] - event.y)
            for _ in fig.getp('axes').values():
                if _._renderer is target:
                    # self.axes(_)  # set curax to this axis, this seems to cause the crash
                    fig.setp(curax=_)
                    ax = _
                    break

        _print('--> fig {} {} @(x, y) {}'.format(fig.getp('number'), hex(id(fig)), (event.x, event.y)), 'ax', hex(id(ax)), 'curax', fig.getp('curax'))
        # _print('axes', fig.getp('axes'))

        return fig, ax

    def _register_bindings(self, vtkWidget):
        'we must register the figure bindings in the backend because we have to have access to the backend properties'
        def _toggle_state(obj, key):
            boolean = obj.getp(key)
            if isinstance(boolean, bool):
                obj.setp(**{key: not boolean})
            else:
                raise TypeError('not a boolean !')

        def _set_camera(ax, **kwargs):
            cam = ax.getp('camera')
            cam.setp(view=3)  # this resets the defaults, expecially azimuth and elevation to None
            # don't set view in the following command because cammode will fail because of the _set_default_view call
            cam.setp(**kwargs, cammode='manual', camtarget=(0, 0, 0))

        def callback(e, ctrl, shift, **kwargs):
            '''
            stackoverflow.com/a/16082411/5584077
            infohost.nmt.edu/tcc/help/pubs/tkinter/web/key-names.html

            Input
            -----
            kwargs: some compatibility information set on the event to comply with the tk reference
            '''

            # compatibility qt/tk
            [setattr(e, _, __) for _, __ in kwargs.items()]

            fig, ax = self._find_poked(e)
            if ctrl:
                axs = (ax,)
            elif shift:
                axs = list(fig.getp('axes').values())

            if 'tk' in VTK_BACKEND.lower():
                kpevent, eargs, ekwargs = 'KeyPressEvent', (e, ctrl, shift), dict()
            else:
                kpevent, eargs, ekwargs = 'keyPressEvent', (e,), dict(filtered=True)

            key = e.keysym.lower()
            print(key, end=' ')

            if ctrl or shift:
                for ax in axs:
                    # print(hex(id(ax)), key)
                    if key == 'r':
                        break  # break and replot
                    elif key == 'i':
                        plotitems = ax.getp('plotitems')
                        plotitems.sort(key=self._cmpPlotProperties)
                        for item in plotitems:
                            for _ in ('linecolor', 'facecolor', 'edgecolor'):
                                try:
                                    # _get_color takes a string and returns a rgb tuple
                                    color = item.getp(_)
                                    newcol = '_' + colsor.lstrip('_')
                                    item.setp(**{_: newcol})
                                except Exception as e:
                                    pass

                        for _ in ('bgcolor', 'fgcolor', 'axiscolor'):
                            try:
                                color = ax.getp(_)
                                newcol = self._invertc(color)
                                ax.setp(**{_: newcol})
                            except Exception as e:
                                pass
                    elif key == 'g':
                        _toggle_state(ax, 'grid')
                    elif key == 'b':
                        _toggle_state(ax, 'box')
                    elif key == 'a':
                        _toggle_state(ax, 'unit')
                    elif key == 'c':
                        cbar = ax.getp('colorbar')
                        _toggle_state(cbar, 'visible')
                    elif key == 'e':
                        [_toggle_state(_, 'edgevisibility') for _ in ax.getp('plotitems')]
                    elif key == 't':
                        cbar = ax.getp('colorbar')
                        _toggle_state(cbar, 'visible')
                    elif key == 's':
                        if False:
                            self.hardcopy('fig.eps', replot=False, magnification=1)
                        else:
                            self.hardcopy('fig.png', replot=False, magnification=4, quality=9)  # pretty good quality withe these setting !
                        return
                    elif key == 'v':
                        self.hardcopy('movie.mp4')
                    # got camtarget value from paraview default
                    #  --------- /     ^
                    # |camera-->|      |(view up)   x(focal point) ---> (direction of projection = view plane normal)
                    #  --------- \
                    elif key in ('kp_4', 'kp_left'):  # +X into the screen, Y up
                        _set_camera(ax, campos=(-1, 0, 0), camup=(0, 1, 0))
                    elif key in ('kp_5', 'kp_begin'):  # +X into the screen, Z up
                        _set_camera(ax, campos=(-1, 0, 0), camup=(0, 0, 1))
                    elif key in ('kp_6', 'kp_right'):  # +Y into the screen, Z up
                        _set_camera(ax, campos=(0, -1, 0), camup=(0, 0, 1))
                    elif key in ('kp_7', 'kp_home'):  # +Y into the screen, X up
                        _set_camera(ax, campos=(0, -1, 0), camup=(1, 0, 0))
                    elif key in ('kp_8', 'kp_up'):  # +Z into the screen, X up
                        _set_camera(ax, campos=(0, 0, -1), camup=(1, 0, 0))
                    elif key in ('kp_9', 'kp_prior'):  # +Z into the screen, Y up
                        _set_camera(ax, campos=(0, 0, -1), camup=(0, 1, 0))
                    elif key in ('kp_1', 'kp_end'):  # toggle perspective between orthographic or parallel
                        cam = ax.getp('camera')
                        # nice one liner to toggle values of a 2 elements list/tuple !
                        cam.setp(camproj=cam._camprojs[1 - cam._camprojs.index(cam.getp('camproj'))])
                    elif key in ('kp_2', 'kp_down'):
                        self.view(2)
                        return
                    elif key in ('kp_3', 'kp_next'):
                        self.view(3)
                        return
                    else:
                        # when a binding is not known, return without replotting, and forward the event
                        getattr(vtkWidget, kpevent)(*eargs, **ekwargs)
                        return
                # only replot at the end
                self._replot(fig, axs)

            else:
                if e.keysym == 'i':
                    if getattr(ax, '_iw', None) is not None:
                        fig._g.iren.SetKeyCode('i')
                        # fig._g.iren.CharEvent()
                        # ax._iw.SetInteractor(fig._g.((iren)
                        # ax._iw.SetCurrentRenderer(ax._renderer)
                        ax._iw.OnChar()
                        # ax._iw.InvokeEvent('EnableEvent') if not ax._iw._on else ax._iw.InvokeEvent('DisableEvent')
                    # self._g.iren.CharEvent()
                    # self._g.iren.SetKeySym('i')
                    # self._g.iren.KeyPressEvent()
                else:
                    # forward the event if not interactive event
                    getattr(vtkWidget, kpevent)(*eargs, **ekwargs)
                return

        ######################################################
        if 'tk' in VTK_BACKEND.lower():
            vtkWidget.bind('<Control-Key>', lambda e: callback(e, 1, 0))
            vtkWidget.bind('<Shift-Key>', lambda e: callback(e, 0, 1))
            vtkWidget.bind('<KeyPress>', lambda e: callback(e, 0, 0))
        else:
            vtkWidget.callback = callback

    def figure(self, *args, **kwargs):
        'Extension of BaseClass.figure: adding a plotting package figure instance as fig._g and create a link to it as self._g'
        fig = BaseClass.figure(self, *args, **kwargs)
        self.name = '[{}] {}'.format(fig.getp('number'), fig.getp('suptitle'))
        try:
            fig._g.root.title(self.name) if 'tk' in VTK_BACKEND.lower() else fig._g.root.setWindowTitle(self.name)
        except:
            # create plotting package figure and save figure instance as fig._g
            _print('creating figure {} in backend'.format(self.name))
            width, height = fig.getp('size')
            if not (width and height):
                width, height = 800, 600
                fig.setp(size=[width, height])
            fig._g = _VTKFigure(self, width, height, title=self.name)
            self._register_bindings(fig._g.vtkWidget)

        self.fig = fig
        self._g = fig._g  # link for faster access

        return fig

    def closefig(self, vtkfig_or_num):
        with _debug('closefig'):
            fig = None
            if type(fig) is int:
                fig = self._figs[vtkfig_or_num]
            else:
                for _ in list(self._figs.values()):
                    _g = getattr(_, '_g', None)
                    if _g is vtkfig_or_num:
                        fig = _
                        break

            if fig:
                # delete the associated vtkfig !
                for _ in list(self._figs):
                    if self._figs[_] is fig:
                        del self._figs[_]
                del fig
                if len(self._figs) < 1:
                    self._master.quit()

                self.figure(max(self._figs) if len(self._figs) > 0 else None)  # raise another figure

    def _setup_axis(self, ax):
        with _debug('axis'):
            self._set_limits(ax)
            self._set_daspect(ax)
            self._set_colormap(ax)
            self._set_caxis(ax)

            # create a renderer for this axis and add it to the current figures renderer window
            ax._renderer = vtkRenderer()
            self._g.renwin.AddRenderer(ax._renderer)

            # Set the renderers background color:
            ax._renderer.SetBackground(*ax.getp('bgcolor'))

            viewport = ax.getp('viewport')
            ax._renderer.SetViewport((0, 0, 1, 1) if not viewport else viewport)
            ax._renderer.RemoveAllViewProps()  # clear current scene
            # axshape = self.gcf().getp('axshape')
            # ax._renderer.SetPixelAspect(axshape[1], axshape[0])

            ax._apd = vtkAppendPolyData()
            if getattr(ax, '_iw', None) is not None:
                if ax._iw._on:  # else iwidget crashes without any information
                    ax._iw.Off()

    def _fix_latex(self, legend):
        'Remove latex syntax a la $, \, {, } etc'
        # General fix of latex syntax (more readable)
        legend = legend.strip().replace('**', '^').replace('$', '').replace('{', '').replace('}', '').replace('\\', '')
        # legend = legend.replace('*', '')
        return legend

    def _replot(self, fig=None, axs=(), hard=False):
        'replot all axes and all plotitems in the backend. NOTE: only the current figure (gcf) is redrawn'
        _print('<replot in backend>')
        # reset the plotting package instance in fig._g now if needed

        if not fig:
            fig = self.fig
        fig_axes = list(fig.getp('axes').values())

        if (axs and all(_ in fig_axes for _ in axs) and len(axs) == len(fig_axes)) or hard:
            if not hard:
                _print('--> hard reset for all the renderers')
            fig._g.hard_reset()
            self._register_bindings(fig._g.vtkWidget)
        else:
            fig._g.soft_reset(axs)

        # suptitle
        suptitle = fig.getp('suptitle')

        nrows, ncols = fig.getp('axshape')
        grid = np.indices((nrows, ncols))
        rows, cols = grid[0].flatten()[::-1], grid[1].flatten()
        for axnr, ax in list(fig.getp('axes').items()):
            if ax.getp('numberofitems') == 0:
                continue
            if axs and ax not in axs:  # then replot only for specified axes
                continue
            # print('--> replot for ax', hex(id(ax)))
            self._ax = ax  # link for faster access
            if nrows != 1 or ncols != 1:
                # create axes in tiled position  this is subplot(nrows,ncols,axnr)
                row, col = rows[axnr - 1], cols[axnr - 1]
                xmin, xmax = col / ncols, (col + 1) / ncols
                ymin, ymax = row / nrows, (row + 1) / nrows
                ax.setp(viewport=[xmin, ymin, xmax, ymax])
                # _print('viewport (xmin, ymin, xmax, ymax)', (xmin, ymin, xmax, ymax))

            self._setup_axis(ax)
            # from now on, ax._renderer and ax._apd are created
            plotitems = ax.getp('plotitems')
            plotitems.sort(key=self._cmpPlotProperties)
            for item in plotitems:
                func = item.getp('function')  # function that produced this item
                if isinstance(item, Line):
                    self._add_line(item)
                elif isinstance(item, Surface):
                    self._add_surface(item, shading=ax.getp('shading'))
                elif isinstance(item, Contours):
                    self._add_contours(item)
                elif isinstance(item, VelocityVectors):
                    self._add_vectors(item)
                elif isinstance(item, Streams):
                    self._add_streams(item)
                elif isinstance(item, Volume):
                    getattr(self, '_add_' + func)(item)

                # legend = self._fix_latex(item.getp('legend'))
                legend = item.getp('legend')
                if legend:
                    # add legend to plot
                    legendActor = vtkLegendBoxActor()
                    legendActor.SetNumberOfEntries(1)
                    # symbol = vtkSphereSource(); symbol.Update()  # for an empty symbol, pass an empty vtkPolyData instance
                    legendActor.SetEntry(0, vtkPolyData(), legend, ax.getp('axiscolor'))
                    self._set_coord_in_system(legendActor.GetPositionCoordinate(), (0, .8), 'VTK_NORMALIZED_VIEWPORT')
                    textProp = legendActor.GetEntryTextProperty()
                    textProp.SetFontSize(textProp.GetFontSize() // 2)
                    if ax.getp('legend_fancybox'):
                        legendActor.BorderOn()
                    ax._renderer.AddActor(legendActor)

            self._set_axis_props(ax)

            if getattr(ax, '_iw', None) is not None:
                # print('after reset', ax._iw)
                if ax._iw._on:
                    print('enabling widget')
                    # fig._g.iren.SetKeyCode('i')
                    if not ax._iw.GetEnabled():
                        ax._iw.On()
                    ax._iw.SetInteractor(fig._g.iren)
                    ax._iw.SetCurrentRenderer(ax._renderer)
                    # fig._g.iren.CharEvent()
                    # fig._g.iren.KeyPressEvent()
                    # ax._iw.OnChar()
                    # ax._iw.On()
                    ax._iw._RemoveObservers()
                    ax._iw._AddObservers()
                    ax._iw.InvokeEvent('EnableEvent')

        if self.getp('show'):
            # display plot on the screen
            if DEBUG:
                _print('<plot data to screen>')
                debug(self, level=0)

        self._g.display(show=self.getp('show'))

    def mainloop(self, **kwargs):
        'blocking call for showing tk widget'
        _print('<mainloop>')

        # closing empty figures, efficient only if there is any plot object !
        for fignum in sorted(list(self._figs.keys()), reverse=True):
            fig = self._figs[fignum]
            if all(not ax.getp('plotitems') for ax in fig.getp('axes').values()):
                _print('figure', fignum, 'is empty')
                _g = getattr(fig, '_g', None)
                if _g:
                    _g.exit()
                else:
                    self.closefig(fignum)

        # re-loop to see if there are plot objects
        not_null = False
        for fignum in sorted(list(self._figs.keys()), reverse=True):
            fig = self._figs[fignum]
            if any(ax.getp('plotitems') for ax in fig.getp('axes').values()):
                not_null = True
                break

        if not_null:
            self.setp(**kwargs)
            self.all_show()

            self._master.mainloop() if 'tk' in VTK_BACKEND.lower() else self._master.exec_()

    def all_show(self):
        _print('<all_show>')
        if self.getp('show'):
            for _, fig in list(self._figs.items()):
                self.figure(fig.getp('number'))
                if any(hasattr(ax, '_iw') and ax._iw for _, ax in list(fig.getp('axes').items())):
                    if 'tk' in fig._g.backend:
                        fig._g.vtkWidget.Start()  # self._g.vtkWidget.Initialize()
                        fig._g.vtkWidget.focus_force()
                        fig._g.vtkWidget.update()
                    else:
                        pass
                self.show()

    def hardcopy(self, filename, **kwargs):
        '''
        Supported extensions in VTK backend:

          * '.ps'  (PostScript)
          * '.eps' (Encapsualted PostScript)
          * '.pdf' (Portable Document Format)
          * '.svg' (Scalable Vector Graphics)
          * '.jpg' (Joint Photographic Experts Group)
          * '.png' (Portable Network Graphics)
          * '.pnm' (Portable Any Map)
          * '.tif' (Tagged Image File Format)
          * '.bmp' (Bitmap Image)

        Optional arguments for JPEG output:

          quality     -- Set the quality of the resulting JPEG image. The
                         argument must be given as an integer between 0 and
                         100, where 100 gives the best quality (but also
                         the largest file). Default quality is 10. Used also
                         for the png writer for the compression level (0-9)

          progressive -- Set whether to use progressive JPEG generation or not

        Optional arguments for PostScript and PDF output:

          vector_file -- If True (default), the figure will be stored as a
                         vector file, i.e., using vtkGL2PSExporter instead
                         of vtkPostScriptWriter (requires VTK to be built
                         with GL2PS support). GL2PS gives much better
                         results, but at a cost of longer generation times
                         and larger files.

          orientation -- Set the orientation to either 'portrait' (default)
                         or 'landscape'. This option only has effect when
                         vector_file is True.

          raster3d    -- If True, this will write 3D props as raster images
                         while 2D props are rendered using vector graphic
                         primitives. Default is False. This option only has
                         effect when vector_file is True.

          compression -- If True, compression will be used when generating
                         PostScript or PDF output. Default is False (no
                         compression). This option only has effect when
                         vector_file is True.
        '''

        with _debug('hardcopy to', filename):
            self.setp(**kwargs)

            compression_or_quality = int(kwargs.get('quality', 9))
            progressive = int(kwargs.get('progressive', True))
            vector_file = int(kwargs.get('vector_file', False))
            landscape = int(True if kwargs.get('orientation', 'portrait').lower() == 'landscape' else False)
            raster3d = int(kwargs.get('raster3d', False))
            compression = int(kwargs.get('compression', True))
            magnification = int(kwargs.get('magnification', 2))

            # scale the fontsize  for text rendering according to magnification
            old_ft = []
            for fig in self._figs.values():
                for ax in fig.getp('axes').values():
                    old_ft.append(ax.getp('fontsize'))
                    ax.setp(fontsize=old_ft[-1] * magnification**.8)

            for _ in ('compression_or_quality', 'progressive', 'vector_file', 'landscape', 'raster3d', 'compression', 'magnification'):
                _print('   ', _, '=', locals()[_])

            if not self.getp('show'):  # don't render to screen
                # print('offscreen')
                off_ren = self._g.renwin.GetOffScreenRendering()
                self._g.renwin.OffScreenRenderingOn()

            if kwargs.get('replot', True):
                self._replot()

            basename, ext = os.path.splitext(filename)
            if not ext:
                # no extension given, assume .ps:
                ext = '.ps'
                filename += ext

            vector_file_formats = {'.ps': 0, '.eps': 1, '.pdf': 2, '.tex': 3, '.svg': 4}
            if vector_file and ext.lower() in vector_file_formats:
                exp = vtkOpenGLGL2PSExporter()
                if DEBUG:
                    exp.DebugOn()
                exp.SetBufferSize(50 * 1024**2)  #  50MB
                exp.SetRenderWindow(self._g.renwin)
                exp.SetFilePrefix(basename)
                exp.SetFileFormat(vector_file_formats[ext.lower()])
                exp.SetCompress(compression)
                exp.SetLandscape(landscape)
                # exp.SetSortToBSP()
                exp.SetSortToSimple()  # less expensive sort algorithm
                exp.DrawBackgroundOn()
                exp.SetWrite3DPropsAsRasterImage(raster3d)
                exp.Write()

            elif ext.lower() in ('.tif', '.tiff', '.bmp', '.pnm', '.png', '.jpg', '.jpeg', '.ps', '.eps', '.avi', '.mp4', '.raw'):
                vtk_image_writers = {
                    '.tif': vtkTIFFWriter(),
                    '.tiff': vtkTIFFWriter(),
                    '.bmp': vtkBMPWriter(),
                    '.pnm': vtkPNMWriter(),
                    '.png': vtkPNGWriter(),
                    '.jpg': vtkJPEGWriter(),
                    '.jpeg': vtkJPEGWriter(),
                    '.ps': vtkPostScriptWriter(),
                    '.eps': vtkPostScriptWriter(),  # gives a normal PS file
                    '.avi': vtkFFMPEGWriter(),
                    '.mp4': vtkFFMPEGWriter(),
                    '.raw': vtkFFMPEGWriter(),
                }
                w2if = vtkWindowToImageFilter()
                w2if.SetMagnification(magnification)
                if magnification > 1:
                    w2if.FixBoundaryOn()
                w2if.SetInput(self._g.renwin)
                if ext.lower() in ('.ps', '.eps'):
                    w2if.SetInputBufferTypeToRGB()  # vtkPostScriptWriter only support 1 or 3 (RGB) components not 4 (RGB + alpha)
                else:
                    w2if.SetInputBufferTypeToRGBA()  # else all items drawn using alpha channel won't appear
                w2if.ReadFrontBufferOff()  # needed to avoid some desktop overlay on linux
                w2if.Update()  # or w2if.Modified(), advised in documentation
                writer = vtk_image_writers[ext.lower()]
                if ext.lower() in ('.png',):
                    writer.SetCompressionLevel(compression_or_quality)  # 0-9, default 5
                if ext.lower() in ('.jpg', '.jpeg'):
                    writer.SetQuality((compression_or_quality + 1) * 10)  # default 10*10 = 100
                    writer.SetProgressive(progressive)
                if ext.lower() in ('.tif', '.tiff'):
                    writer.SetCompressionToDeflate()
                if ext.lower() in ('.avi', '.mp4', '.raw'):
                    writer.SetBitRate(1024 * 1024 * 30)
                    writer.SetBitRateTolerance(1024 * 1024 * 3)
                    if ext.lower() in ('.raw',):
                        writer.CompressionOff()

                    class vtkTimerCallback:
                        'vtk.org/Wiki/VTK/Examples/Python/Animation'

                        def __init__(self):
                            self.timer_count = 0

                        def execute(self, obj, event):
                            print(self.timer_count)
                            self.actor.SetPosition(self.timer_count, self.timer_count, 0)
                            iren = obj
                            iren.GetRenderWindow().Render()
                            self.timer_count += 1

                    cb = vtkTimerCallback()
                    cb.actor = self._ax._renderer.GetActors()[0]

                    self._g.iren.AddObserver('TimerEvent', cb.execute)
                    self._g.iren.CreateRepeatingTimer(100)
                    '''
                    this is not correct, we must add the timer during the _replot() call
                    in fact, just before fig._g.vtkWidget.Start() in all_show()
                    '''
                    self._g.iren.Start()
                    writer.Start()

                writer.SetFileName(filename)
                writer.SetInputConnection(w2if.GetOutputPort())

                'here we should animate the movie'
                writer.Write()

                if ext.lower() in ('.avi', '.mp4', '.raw'):
                    writer.End()
            else:
                msg = 'hardcopy: Extension {} is currently not supported.'.format(ext)
                print(msg)
                raise TypeError(msg)

            # restore OffScreenRendering state
            if not self.getp('show'):
                self._g.renwin.SetOffScreenRendering(off_ren)

            # reset fontsize
            for fig in self._figs.values():
                for ax in fig.getp('axes').values():
                    ax.setp(fontsize=old_ft.pop())

    # reimplement color maps and other methods (if necessary) like clf,
    # closefig, and closefigs here.

    def vtk_lut_from_mpl(self, cmap_or_name='viridis'):
        'construct a vtkLookupTable from a string or a LinearSegmentedColormap'
        lut = vtkLookupTable()
        if isinstance(cmap_or_name, str):
            _data = _cmaps[cmap_or_name].colors
        elif isinstance(cmap_or_name, (list, tuple, np.ndarray)):
            _data = cmap_or_name
        else:  # case LinearSegmentedColormap
            _data = cmap_or_name(range(cmap_or_name.N))[:, :3]  # remove alpha channel from RGBA
        lut.SetNumberOfTableValues(len(_data))
        [lut.SetTableValue(_, *_data[_]) for _ in range(len(_data))]
        return lut

    def hsv(self, m=64):
        lut = vtkLookupTable()
        lut.SetHueRange(0, 1)
        lut.SetSaturationRange(1, 1)
        lut.SetValueRange(1, 1)
        lut.SetNumberOfColors(m)
        lut.Build()
        return lut

    def gray(self, m=64):
        lut = vtkLookupTable()
        lut.SetHueRange(0, 0)
        lut.SetSaturationRange(0, 0)
        lut.SetValueRange(0, 1)
        lut.SetNumberOfColors(m)
        lut.Build()
        return lut

    def hot(self, m=64):
        lut = vtkLookupTable()
        inc = .01175
        lut.SetNumberOfColors(256)
        i = 0
        r = .0; g = .0; b = .0
        while r <= 1.:
            lut.SetTableValue(i, r, g, b, 1)
            r += inc; i += 1
        r = 1.
        while g <= 1.:
            lut.SetTableValue(i, r, g, b, 1)
            g += inc; i += 1
        g = 1.
        while b <= 1:
            if i == 256:
                break
            lut.SetTableValue(i, r, g, b, 1)
            b += inc; i += 1
        lut.Build()
        return lut

    def flag(self, m=64):
        assert m % 4 == 0, 'flag: the number of colors must be a multiple of 4.'
        lut = vtkLookupTable()
        lut.SetNumberOfColors(m)
        # the last parameter alpha is set to 1 by default  in method declaration
        for _ in range(0, m, 4):
            lut.SetTableValue(_, 1, 0, 0, 1)      # red
            lut.SetTableValue(1 + _, 1, 1, 1, 1)  # white
            lut.SetTableValue(2 + _, 0, 0, 1, 1)  # blue
            lut.SetTableValue(3 + _, 0, 0, 0, 1)  # black
        lut.Build()
        return lut

    def jet(self, m=64):
        # blue, cyan, green, yellow, red, black
        lut = vtkLookupTable()
        lut.SetNumberOfColors(m)
        lut.SetHueRange(.667, 0)
        lut.Build()
        return lut

    def spring(self, m=64):
        lut = vtkLookupTable()
        lut.SetNumberOfColors(m)
        lut.SetHueRange(0, .17)
        lut.SetSaturationRange(.5, 1)
        lut.SetValueRange(1, 1)
        lut.Build()
        return lut

    def summer(self, m=64):
        lut = vtkLookupTable()
        lut.SetNumberOfColors(m)
        lut.SetHueRange(.47, .17)
        lut.SetSaturationRange(1, .6)
        lut.SetValueRange(.5, 1)
        lut.Build()
        return lut

    def winter(self, m=64):
        lut = vtkLookupTable()
        lut.SetNumberOfColors(m)
        lut.SetHueRange(.8, .42)
        lut.SetSaturationRange(1, 1)
        lut.SetValueRange(.6, 1)
        lut.Build()
        return lut

    def autumn(self, m=64):
        lut = vtkLookupTable()
        lut.SetNumberOfColors(m)
        lut.SetHueRange(0, .15)
        lut.SetSaturationRange(1, 1)
        lut.SetValueRange(1, 1)
        lut.Build()
        return lut

    # Now we add the doc string from the methods in BaseClass to the
    # methods that are reimplemented in this backend:
    for cmd in BaseClass._matlab_like_cmds:
        if '__' not in cmd and hasattr(BaseClass, cmd):
            m1 = eval('BaseClass.{}'.format(cmd))
            try:
                m2 = eval('{}'.format(cmd))
            except NameError:
                pass
            else:
                if m1.__doc__ != m2.__doc__:
                    if m2.__doc__ is None:
                        m2.__doc__ = ''
                    m2.__doc__ = m1.__doc__ + m2.__doc__

plt = VTKBackend()   # create backend instance
use(plt, globals())  # export public namespace of plt to globals()
backend = os.path.splitext(os.path.basename(__file__))[0][:-1]

############
# OBSOLETE #
############

# self._g.vtkWidget.bind('<KeyPress-a>', lambda e, s=lineWidget: s.InvokeEvent(vtkCommand.StartInteractionEvent))

# def foo2(e):
#     print(repr(e.char))
#     self._g.vtkWidget.KeyPressEvent(e, 0, 0)

# self._g.vtkWidget.bind('<KeyPress-u>', foo2)

# def Keypress(obj, event):
#     key = obj.GetKeySym()
#     if key == 'c':
#         print('c was pressed')

#     print(repr(event.char))

# self.lineWidget.AddObserver('KeyPressEvent', Keypress)

# def foo(e):
#     print(repr(e.char))
# self.streamline.VisibilityOn()
#     print('done')

# self._g.vtkWidget.bind('<KeyPress-l>', foo)
# wr = vtkPolyDataWriter()
# wr.SetInputData(seeds.GetOutput())
# wr.SetFileName('/home/tb246060/Bureau/seeds.vtk')
# wr.Write()


# wr = vtkStructuredGridWriter()
# wr.SetInputData(sgrid.GetOutput(2))
# wr.SetFileName('/home/tb246060/Bureau/sgrid.vtk')
# wr.Write()


# sgrid = vtkPointDataToCellData()
# sgrid.SetInputConnection(ps.GetOutputPort(2))
# sgrid.PassPointDataOn()
# sgrid.Update()


# self._set_actor_properties(item, streamline)
# self._ax._renderer.AddActor(streamline)
# self._set_actor_properties(item, outlineActor)
# self._ax._renderer.AddActor(outlineActor)

# print('streamer', streamer.GetOutput())
# rt = streamer.GetOutput().GetCellData().GetArray('ReasonForTermination')
# print('ReasonForTermination', rt)

# rf = vtkRibbonFilter()
# rf.SetInputConnection(streamer.GetOutputPort())
# rf.SetWidth(.1)
# rf.SetWidthFactor(5)
# streamMapper = vtkPolyDataMapper()
# streamMapper.SetInputConnection(rf.GetOutputPort())
# streamMapper.SetScalarRange(sgrid.GetOutput().GetScalarRange())
# streamline = vtkActor()
# streamline.SetMapper(streamMapper)
# streamline.VisibilityOff()

# outline = vtkStructuredGridOutlineFilter()
# outline.SetInputData(pl3d_output)
# outlineMapper = vtkPolyDataMapper()
# outlineMapper.SetInputConnection(outline.GetOutputPort())
# outlineActor = vtkActor()
# outlineActor.SetMapper(outlineMapper)

# def BeginInteraction(obj, event):
# print('.')
#     streamline.VisibilityOn()

# def GenerateStreamlines(obj, event):
# print(',')
#     obj.GetPolyData(seeds2)
#     streamer.Update()
#     print(streamer.GetOutput())
#     self._g.renwin.Render()

# lineWidget.SetInteractor(self._g.renwin.GetInteractor())

# lineWidget.AddObserver('StartInteractionEvent', BeginInteraction)
# lineWidget.AddObserver('InteractionEvent', GenerateStreamlines)


##########################
# fully functionnal structuredgrid with programmable source
#########################
# sgrid = vtkProgrammableSource()
# sgrid.DebugOn()

# def add_vect():
#     output = sgrid.GetStructuredGridOutput()
#     output.SetDimensions(item.getp('dims'))
#     output.SetPoints(points)
#     output.GetPointData().SetVectors(vectors)
#     output.GetPointData().SetScalars(scalars)

# sgrid.SetExecuteMethod(add_vect)
# sgrid.Update()


# self.root.bind('<Key>', self.key)

# def key(self, event):
#     print('pressed', repr(event.char))
#     if repr(event.char) == 'q':
#         self.close(event)


# glyph codes from vtkGlyphSource2D.h
# VTK_NO_GLYPH 0
# VTK_VERTEX_GLYPH 1
# VTK_DASH_GLYPH 2
# VTK_CROSS_GLYPH 3
# VTK_THICKCROSS_GLYPH 4
# VTK_TRIANGLE_GLYPH 5
# VTK_SQUARE_GLYPH 6
# VTK_CIRCLE_GLYPH 7
# VTK_DIAMOND_GLYPH 8
# VTK_ARROW_GLYPH 9
# VTK_THICKARROW_GLYPH 10
# VTK_HOOKEDARROW_GLYPH 11
# VTK_EDGEARROW_GLYPH 12

# +X

# renderView1.CameraPosition = [-3.2903743041222895, 0.0, 0.0]
# renderView1.CameraFocalPoint = [1e-20, 0.0, 0.0]
# renderView1.CameraViewUp = [0.0, 0.0, 1.0]
# renderView1.CameraParallelScale = 0.8516115354228021

# +Y
# renderView1.CameraPosition = [0.0, -3.2903743041222895, 0.0]
# renderView1.CameraFocalPoint = [0.0, 1e-20, 0.0]
# renderView1.CameraViewUp = [0.0, 0.0, 1.0]
# renderView1.CameraParallelScale = 0.8516115354228021

# +Z
# renderView1.CameraPosition = [0.0, 0.0, -3.2903743041222895]
# renderView1.CameraFocalPoint = [0.0, 0.0, 1e-20]
# renderView1.CameraParallelScale = 0.8516115354228021

# if axis.getp('camera'):
#     if axis.getp('camera').getp('camshare'):
#         camera = axis.getp('camera').getp('camshare')
#         break

# if camshare is not None:
#     camera = camshare
#     ax._renderer.SetActiveCamera(camera)
#     ax._camera = camera
#     return
# else:
#     # existing shared camera from another axis or newcamera if None exists
#     camera = vtkCamera()
#     for _, axis in list(fig.getp('axes').items()):
#         if axis.getp('camera'):
#             if axis.getp('camera').getp('camshare'):
#                 camera = axis.getp('camera').getp('camshare')
#                 break

# s = vtk.vtkSphereSource()
# e = vtk.vtkElevationFilter()
# e.SetInputConnection(s.GetOutputPort())
# e.Update()
# from vtk.util.numpy_support import vtk_to_numpy
# vtk_to_numpy(e.GetOutput())
# from vtk.numpy_interface import dataset_adapter as dsa
# sphere = dsa.WrapDataObject(e.GetOutput())


# writer = vtkStructuredGridWriter()
# writer.SetFileName('_add_threshold.vtk')
# writer.SetInputConnection(sgrid.GetOutputPort())
# writer.Write()


# probe = vtkProbeFilter()
# probe.SetSourceConnection(threshold.GetOutputPort())
# probe.SetInputData(sgrido)
# probe.Update()  # because of GetImageDataOutput()
# # check for any missed points, ref: vtk.org/Wiki/Demystifying_the_vtkProbeFilter
# assert(probe.GetOutput().GetNumberOfPoints() == probe.GetValidPoints().GetNumberOfTuples())
# print(probe.GetImageDataOutput())

# img_source = vtkAlgorithmSource(probe.GetImageDataOutput(), 'vtkImageData')

# def all_exit(self):
#     for _, fig in list(self._figs.items()):
#         self.figure(fig.getp('number'))
#         self._g.exit()
#     self._master.quit()
#     # self.master.destroy()  # do not destroy, in order to create other figures ...

# vtkDataSetAttributes.SCALARS or 'scalars'
# <...>(int idx, int port, int connection, int fieldAssociation, const char *name)
# threshold.SetInputArrayToProcess(0, 0, 0, vtkDataObject.FIELD_ASSOCIATION_POINTS, 'scalars')
# threshold.SetInputArrayToProcess(0, 0, 0, vtkDataObject.FIELD_ASSOCIATION_POINTS, vtkDataSetAttributes.SCALARS)
