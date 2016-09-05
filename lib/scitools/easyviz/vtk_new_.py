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
Python bindings for VTK.

Notes:

- filled contours (contourf) doesn't look good in VTK 5..

'''

from __future__ import print_function
from .common import *
from scitools.globaldata import DEBUG, VERBOSE, OPTIMIZATION
from scitools.misc import check_if_module_exists
from scitools.numpyutils import allclose
from .misc import _update_from_config_file
from .colormaps import _magma_data, _inferno_data, _plasma_data, _viridis_data
import numpy as np
from copy import deepcopy
import os
import sys

# change these to suit your needs.
major_minor = '.'.join(map(str, (sys.version_info.major, sys.version_info.minor)))
inc_dirs = [os.path.expandvars('$CONDA_PREFIX/include/vtk-7.0')]
lib_dirs = [os.path.join(os.environ['CONDA_PREFIX'], 'lib/python{}/site-packages/vtk'.format(major_minor)), '/usr/lib']

sys.path.extend(lib_dirs)
# print(sys.path)

check_if_module_exists('vtk', msg='You need to install the vtk package.', abort=False)
import vtk
# print(dir(vtk))

# check_if_module_exists('tkinter', msg='You need to install the Tkinter package.')
try:
    import tkinter
except:
    import Tkinter as tkinter
# use old behavior in Tkinter module to get around issue with Tcl
# (more info: http://www.python.org/doc/2.3/whatsnew/node18.html)
# tkinter.wantobjects = 0

try:
    import vtkTkRenderWidget
except:
    from vtk.tk import vtkTkRenderWidget
    # print('from vtk.tk import vtkTkRenderWidget')

try:
    import vtkTkRenderWindowInteractor
except:
    from vtk.tk import vtkTkRenderWindowInteractor
    # print('from vtk.tk import vtkTkRenderWindowInteractor')


from vtk.util.vtkAlgorithm import VTKPythonAlgorithmBase

_vtk_options = {'mesa': 0,
                'vtk_inc_dir': inc_dirs,
                'vtk_lib_dir': lib_dirs}
_update_from_config_file(_vtk_options, section='vtk')

if _vtk_options['mesa']:
    _graphics_fact = vtk.vtkGraphicsFactory()
    _graphics_fact.SetOffScreenOnlyMode(1)
    _graphics_fact.SetUseMesaClasses(1)
    _imaging_fact = vtk.vtkImagingFactory()
    _imaging_fact.SetUseMesaClasses(1)
    del _graphics_fact
    del _imaging_fact

if OPTIMIZATION == 'numba':
    try:
        import numba
    except ImportError:
        print('Numba not available. Optimization turned off.')


class _VTKFigure:

    def __init__(self, plt, width=800, height=600, title=''):
        # create the GUI:
        self.plt = plt
        self.width = width
        self.height = height
        self.root = tkinter.Toplevel(plt._master)
        self.root.title(title)
        self.root.protocol('WM_DELETE_WINDOW', self.exit)
        self.root.minsize(200, 200)
        self.root.geometry('{}x{}'.format(width, height))
        self.root.withdraw()
        self.frame = tkinter.Frame(self.root)  # relief='sunken', bd=2
        self.frame.pack(side='top', fill='both', expand='true')
        self._init()

    def _init(self):
        self.tkw = vtkTkRenderWindowInteractor.vtkTkRenderWindowInteractor(self.frame, width=self.width, height=self.height)
        self.tkw.pack(expand='true', fill='both')
        self.renwin = self.tkw.GetRenderWindow()
        self.renwin.SetSize(self.width, self.height)
        self.iren = self.renwin.GetInteractor()
        # force trackball mode, see also vtkInteractorObserver::OnChar or vtk3DWidget
        self.iren.SetInteractorStyle(vtk.vtkInteractorStyleTrackballCamera())
        self.tkw.focus_force()  # needed for the callback to work
        self.tkw.update()
        print('<_init>') if DEBUG else None

    def hard_reset(self):
        # is calling del removing the window from memory, not only from namespace ?
        # for now this is the only way for the interactive widgets to work when issuing a replot ...
        # if we could avoid deleting the tkw it'll be great ...
        self.clear()
        self._init()
        print('<hard reset>') if DEBUG else None

    def soft_reset(self, axs=()):
        for ax in axs:  # remove renderer associated to axis
            ren = getattr(ax, '_renderer', None)
            if ren and self.renwin.HasRenderer(ren):
                self.renwin.RemoveRenderer(ren)

        # renderers = self.renwin.GetRenderers()
        # ren = renderers.GetFirstRenderer()
        # print('target axs', [hex(id(_)) for _ in axs])
        # ax_ren = list(zip([hex(id(_)) for _ in axs], [hex(id(getattr(_, '_renderer', None))) for _ in axs]))
        # while ren is not None:
        #     print(ax_ren)
        #     if axs and any(ren == getattr(_, '_renderer', False) for _ in axs):
        #         print('remove', hex(id(ren)))
        #         self.renwin.RemoveRenderer(ren)
        #     ren = renderers.GetNextItem()

        # else iwidget crashes without any information
        # for ax in axs:
        #     if getattr(ax, '_iw', None) is not None:
        #         # print('old is')
        #         # print('\n'.join(['{}:{}'.format(_, ax._iw.__dict__[_]) for _ in ax._iw.__dict__ if not isinstance(ax._iw.__dict__[_], (Axis, Figure))]))
        #         if ax._iw.GetEnabled():
        #             ax._iw.InvokeEvent('DisableEvent')
        #             ax._iw._on = True  # fake the widget by setting widget On
            # del ax._iw
            # for attr in ('_apd', '_renderer'):
            #     _ = getattr(ax, attr, None)
            #     del _
        print('<soft reset>') if DEBUG else None

    def display(self, show):
        if show:
            self.root.deiconify()  # raise window
        self.root.update()         # update window
        self.render()
        print('<display>') if DEBUG else None

    def render(self):
        # full pipeline update (is it really necessary ?, tb added)
        if hasattr(self.plt, '_ax'):
            self.plt._ax._apd.Update()

        renderers = self.renwin.GetRenderers()  # first we render each of the axis renderers
        ren = renderers.GetFirstRenderer()
        while ren is not None:
            ren.Render()
            ren = renderers.GetNextItem()
        # then we render the complete scene
        self.renwin.Render()
        print('<render>') if DEBUG else None

    def clear(self):
        self.renwin.Finalize()
        if self.iren:
            self.iren.TerminateApp()
            del self.iren
        del self.renwin
        self.root.withdraw()
        self.tkw.forget()
        print('<clear>') if DEBUG else None

    def exit(self):
        self.clear()
        self.frame.forget()
        # self.root.destroy()
        self.plt.closefig(self)
        print('<exit>') if DEBUG else None

    def set_size(self, width, height):
        self.root.geometry('{}x{}'.format(width, height))
        self.root.update()

    def __str__(self):
        return '\n'.join(['{}:{}'.format(k, v) for (k, v) in self.__dict__.items()])


class vtkAlgorithmSource(VTKPythonAlgorithmBase):

    def __init__(self, data=None, outputType='vtkStructuredGrid'):
        super().__init__(nInputPorts=0, nOutputPorts=1, outputType=outputType)
        self.data = data
        self.outputType = outputType
        self.Update()

    def RequestData(self, request, inInfo, outInfo):
        if self.outputType == 'vtkStructuredGrid':
            dset = vtk.vtkStructuredGrid
        elif self.outputType == 'vtkPolyData':
            dset = vtk.vtkPolyData
        opt = dset.GetData(outInfo)
        opt.ShallowCopy(self.data)
        return 1

    def GetOutput(self):
        return self.GetOutputDataObject(0)


def vtkInteractiveWidget(parent, **kwargs):
    if 'boxwidget' in parent.lower():
        klass, plane = vtk.vtkBoxWidget, vtk.vtkPlanes()
    elif 'implicitplanewidget' in parent.lower():
        klass, plane = vtk.vtkImplicitPlaneWidget, vtk.vtkPlane()
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
            if isinstance(self, vtk.vtkBoxWidget):
                self._t = vtk.vtkTransform()
                if isinstance(old, vtk.vtkBoxWidget):
                    old.GetTransform(self._t)
            elif isinstance(self, vtk.vtkImplicitPlaneWidget):
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
            if isinstance(self, vtk.vtkBoxWidget):
                self.GetOutlineProperty().SetColor(self.ax.getp('axiscolor'))
                self.RotationEnabledOff()  # we want a bow aligned with the ax, so no rotation allowed
                self.SetTransform(self._t)
            elif isinstance(self, vtk.vtkImplicitPlaneWidget):
                [_.SetColor(self.ax.getp('axiscolor')) for _ in (self.GetOutlineProperty(), self.GetEdgesProperty())]
                self._pd = vtk.vtkPolyData()

        def _GetPlane(self):
            if isinstance(self, vtk.vtkBoxWidget):
                self.GetPlanes(self._p)
            elif isinstance(self, vtk.vtkImplicitPlaneWidget):
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
            if isinstance(self, vtk.vtkBoxWidget):
                self.GetTransform(self._t)
            elif isinstance(self, vtk.vtkImplicitPlaneWidget):
                self.GetPolyData(self._pd)
                pts = self._pd.GetPoints()
                if pts:
                    self._b = pts.GetBounds()

            # set other widgets bounds/transform
            for ax in list(self.fig.getp('axes').values()):
                if ax == self.ax:
                    continue
                if ax._iw is not None:
                    if all(isinstance(_, vtk.vtkBoxWidget) for _ in (self, ax._iw)):
                        ax._iw._t = self._t
                        ax._iw.SetTransform(self._t)
                        ax._iw.InvokeEvent('InteractionEvent')
                    elif all(isinstance(_, vtk.vtkImplicitPlaneWidget) for _ in (self, ax._iw)):
                        ax._iw._pd = self._pd
                        ax._iw._b = self._b
                        ax._iw.PlaceWidget(ax._iw._b)
                        ax._iw.InvokeEvent('InteractionEvent')

        def __str__(self):
            return '\n'.join(['{}:{}'.format(k, v) for (k, v) in self.__dict__.items()])

    return _vtkInteractiveWidget(plane, **kwargs)


class VTKBackend(BaseClass):

    def __init__(self):
        super().__init__()
        self._init()

    def _invertc(self, color):
        '''invert rgb colors, pass if str or anything else'''
        try:
            if len(color) == 3:
                return tuple(1 - _ for _ in color)
        except:
            pass

    def _init(self, *args, **kwargs):
        '''Perform initialization that is special for this backend.'''

        self._master = tkinter.Tk()
        self._master.withdraw()
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
        '''set linear or logarithmic (base 10) axis scale'''
        print('<scales>') if DEBUG else None

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
        '''Add text labels for x-, y-, and z-axis.'''
        xlabel, ylabel, zlabel = ax.getp('xlabel'), ax.getp('ylabel'), ax.getp('zlabel')
        print('<labels>') if DEBUG and (xlabel or ylabel or zlabel) else None
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
        '''Add a title at the top of the axis'''
        # title = self._fix_latex(ax.getp('title'))
        title = ax.getp('title')
        if title:
            print('<title>') if DEBUG else None
            tprop = vtk.vtkTextProperty()
            tprop.BoldOff()
            tprop.SetFontSize(ax.getp('fontsize'))
            tprop.SetColor(ax.getp('fgcolor'))
            tprop.SetFontFamilyToArial()
            tprop.SetVerticalJustificationToTop()
            tprop.SetJustificationToCentered()
            tmapper = vtk.vtkTextMapper()
            tmapper.SetInput(title)
            tmapper.SetTextProperty(tprop)
            tactor = vtk.vtkActor2D()
            tactor.SetMapper(tmapper)
            tactor.GetPositionCoordinate().SetCoordinateSystemToView()
            tactor.GetPositionCoordinate().SetValue(.0, .95)
            ax._renderer.AddActor(tactor)

    def _set_limits(self, ax):
        '''Set axis limits in x, y, and z direction.'''
        print('<axis limits>') if DEBUG else None

        mode = ax.getp('mode')
        if mode == 'auto':
            # let plotting package set 'nice' axis limits in the x, y,
            # and z direction. If this is not automated in the plotting
            # package, one can use the following limits:
            xmin, xmax, ymin, ymax, zmin, zmax = ax.get_limits()
        elif mode == 'manual':
            # (some) axis limits are frozen
            xmin = ax.getp('xmin')
            xmax = ax.getp('xmax')
            if xmin is not None and xmax is not None:
                # set x-axis limits
                pass
            else:
                # let plotting package set x-axis limits or use
                xmin, xmax = ax.getp('xlim')

            ymin = ax.getp('ymin')
            ymax = ax.getp('ymax')
            if ymin is not None and ymax is not None:
                # set y-axis limits
                pass
            else:
                # let plotting package set y-axis limits or use
                ymin, ymax = ax.getp('ylim')

            zmin = ax.getp('zmin')
            zmax = ax.getp('zmax')
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

        limits = [xmin, xmax, ymin, ymax, zmin, zmax]
        ax._limits = (xmin, xmax, ymin, ymax, zmin, zmax)

    def _set_position(self, ax):
        '''set axes position'''
        rect = ax.getp('viewport')
        if rect:
            # axes position is defined. In Matlab rect is defined as [left,bottom,width,height], where the four parameters are location values between 0 and 1 ((0,0) is the lower-left corner and (1,1) is the upper-right corner).
            # NOTE: This can be different in the plotting package.
            pass

    def _set_daspect(self, ax):
        '''set data aspect ratio'''
        dar = ax.getp('daspect')  # dar is a list (len(dar) is 3).
        # the axis limits are stored as ax._limits
        l = list(ax._limits)
        l[0] /= dar[0]; l[1] /= dar[0]
        l[2] /= dar[1]; l[3] /= dar[1]
        l[4] /= dar[2]; l[5] /= dar[2]
        ax._scaled_limits = tuple(l)

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
        '''
        Use either the default Cartesian coordinate system or a matrix coordinate system.
        '''

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
        '''turn box around axes boundary on or off, for vtk we use it to plot the axes'''
        # see cubeAxes.py
        if ax.getp('box'):
            print('<box>') if DEBUG else None
            normals = vtk.vtkPolyDataNormals()
            normals.SetInputConnection(ax._apd.GetOutputPort())
            outline = vtk.vtkOutlineFilter()
            outline.SetInputConnection(normals.GetOutputPort())
            mapOutline = vtk.vtkPolyDataMapper()
            mapOutline.SetInputConnection(outline.GetOutputPort())
            outlineActor = vtk.vtkActor()
            outlineActor.SetMapper(mapOutline)
            outlineActor.GetProperty().SetColor(0, 0, 0)
            tprop = vtk.vtkTextProperty()
            tprop.SetColor(1, 1, 1)
            tprop.ShadowOn()
            axes = vtk.vtkCubeAxesActor2D()
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
        '''turn grid lines on or off, for vtk we use this to plot the grid points'''
        if ax.getp('grid'):
            print('<grid>') if DEBUG else None
            # turn grid lines on
            geom = vtk.vtkStructuredGridGeometryFilter()
            geom.SetInputConnection(self.sgrid.GetOutputPort())
            mapper = vtk.vtkPolyDataMapper()
            mapper.SetInputConnection(geom.GetOutputPort())
            mapper.ScalarVisibilityOff()
            # mapper.SetLookupTable(self._ax._colormap)  # why use a colormap on grid points ?
            actor = vtk.vtkActor()
            actor.SetMapper(mapper)
            actor.GetProperty().SetColor(*ax.getp('axiscolor'))
            ax._renderer.AddActor(actor)
            ax._apd.AddInputConnection(geom.GetOutputPort())
        else:
            pass

    def _set_hidden_line_removal(self, ax):
        '''turn on/off hidden line removal for meshes'''
        if ax.getp('hidden'):
            print('<hidden line removal>') if DEBUG else None
            # turn hidden line removal on
            pass
        else:
            pass

    def _set_colorbar(self, ax):
        '''add a colorbar to the axis'''
        cbar = ax.getp('colorbar')
        if cbar.getp('visible'):
            print('<colorbar>') if DEBUG else None
            cbar_title = cbar.getp('cbtitle')
            # TODO: position the scalarbar actor according to cbar_location
            cbar_location = self._colorbar_locations[cbar.getp('cblocation')]
            scalarBar = vtk.vtkScalarBarActor()
            scalarBar.SetLookupTable(ax._colormap)
            scalarBar.SetTitle(cbar.getp('cbtitle'))
            scalarBar.SetOrientationToHorizontal()
            ax._renderer.AddActor(scalarBar)
        else:
            pass

    def _set_caxis(self, ax):
        '''set the color axis scale'''
        print('<caxis>') if DEBUG else None

        if ax.getp('caxismode') == 'manual':
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
        '''set the colormap'''
        print('<colormap>') if DEBUG else None

        cmap = ax.getp('colormap')
        # cmap is plotting package dependent
        if not isinstance(cmap, vtk.vtkLookupTable):
            cmap = self.viridis()  # use default colormap
        ax._colormap = cmap

    def _set_view(self, ax):
        '''set viewpoint specification'''
        print('<view>') if DEBUG else None

        def print_cam(camera, msg):
            names = ('pos', 'viewup', 'proj_dir', 'focalpoint', 'viewangle', 'plane_norm', 'wincenter', 'viewshear', 'orientation', 'orientationWXYZ', 'roll')
            props = [getattr(camera, _)() for _ in ('GetPosition', 'GetViewUp', 'GetDirectionOfProjection', 'GetFocalPoint', 'GetViewAngle', 'GetViewPlaneNormal', 'GetWindowCenter', 'GetViewShear', 'GetOrientation', 'GetOrientationWXYZ', 'GetRoll')]
            print(' '.join([str(hex(id(camera))), msg, '.' * 25]))
            for name, prop in zip(names, props):
                print(name, prop, end=' ')
            print()

        # unit axes
        if ax.getp('unit'):
            axes = vtk.vtkAxesActor()
            [_.GetTextActor().SetTextScaleModeToNone() for _ in (axes.GetXAxisCaptionActor2D(), axes.GetYAxisCaptionActor2D(), axes.GetZAxisCaptionActor2D())]
            # axes.SetScale(.5)
            ax._renderer.AddActor(axes)

        cam = ax.getp('camera')
        view, focalpoint, position, upvector = cam.getp('view'), cam.getp('camtarget'), cam.getp('campos'), cam.getp('camup')
        camroll, viewangle = cam.getp('camroll'), cam.getp('camva')

        camera = vtk.vtkCamera()
        for axis in self.gcf().getp('axes').values():
            _ = getattr(axis, '_camera', None)
            if _ is not None:
                # update local camera with the one from
                # cam.setp(**axis.getp('camera')._prop)
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
        print('<axis properties>') if DEBUG else None
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
        '''return True if data limits is inside axis limits'''
        slim = self._ax._scaled_limits
        dlim = data.GetBounds()
        for i in range(0, len(slim), 2):
            if dlim[i] < slim[i] and not allclose(dlim[i], slim[i]):
                return False
        for i in range(1, len(slim), 2):
            if dlim[i] > slim[i] and not allclose(dlim[i], slim[i]):
                return False
        return True

    def _cut_data(self, data, item):
        '''return cutted data if limits is outside (scaled) axis limits'''
        data.Update(); datao = data.GetOutput()
        islice = item.getp('islice')

        # data boundaries clipper
        box = vtk.vtkBox()
        box.SetBounds(self._ax._scaled_limits)

        clipper = vtk.vtkClipPolyData()
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

            iclipper = vtk.vtkClipPolyData()
            iclipper.SetInputConnection(data.GetOutputPort())
            iclipper.SetClipFunction(self._ax._iw._p)
            iclipper.SetValue(0)
            iclipper.InsideOutOn()

            def pw_interaction(obj, event):
                # see www.python.org/dev/peps/pep-3104 for nonlocal kw
                obj._GetPlane()

            def pw_start_interaction(obj, event):
                if isinstance(obj, vtk.vtkBoxWidget):
                    obj.OutlineCursorWiresOn()
                    obj.GetHandleProperty().SetOpacity(.5)
                obj.GetOutlineProperty().SetOpacity(.5)

            def pw_end_interaction(obj, event):
                if isinstance(obj, vtk.vtkBoxWidget):
                    obj.OutlineCursorWiresOff()
                    obj.GetHandleProperty().SetOpacity(.2)
                obj.GetOutlineProperty().SetOpacity(0)
                obj._SaveWidget()

            def pw_enable(obj, event):
                nonlocal iclipper, clipper
                # TODO: restore the pwidget parameters
                clipper.SetInputConnection(iclipper.GetOutputPort())
                obj._on = True
                print('enabling')
                pw_interaction(obj, event)
                pw_end_interaction(obj, event)

            def pw_disable(obj, event):
                nonlocal data, clipper
                obj._on = False
                print('disabling')
                clipper.SetInputConnection(data.GetOutputPort())
                obj._SaveWidget()

            for _ in (pw_interaction, pw_start_interaction, pw_end_interaction, pw_enable, pw_disable):
                setattr(self._ax._iw, _.__name__, _)

            self._ax._iw._AddObservers()

            pw_interaction(self._ax._iw, None)  # in order to avoid 'Please define points and/or normals!' errors

        return clipper

    def _set_shading(self, item, source, actor):
        '''shading + mesh contour'''
        shading = self._ax.getp('shading')
        print('<shading>') if DEBUG else None

        if shading == 'interp':
            actor.GetProperty().SetInterpolationToGouraud()
        elif shading == 'flat':
            actor.GetProperty().SetInterpolationToFlat()
        else:
            actor.GetProperty().SetInterpolationToPhong()
            edges = vtk.vtkExtractEdges()
            edges.SetInputConnection(source.GetOutputPort())
            mapper = vtk.vtkPolyDataMapper()
            mapper.SetInputConnection(edges.GetOutputPort())
            mapper.ScalarVisibilityOff()
            mapper.SetResolveCoincidentTopologyToPolygonOffset()

            edgecolor = self._colors.get(item.getp('edgecolor'), None)
            if edgecolor is None:
                # try items linecolor property:
                edgecolor = self._colors.get(item.getp('linecolor'), None)

            if edgecolor is not None:
                mesh = vtk.vtkActor()
                mesh.SetMapper(mapper)
                mesh.GetProperty().SetColor(edgecolor)
                self._ax._renderer.AddActor(mesh)

    def _set_actor_properties(self, item, actor):
        # set line properties:
        color = self._get_color(item.getp('linecolor'), (0, 0, 1))
        actor.GetProperty().SetColor(color)
        if item.getp('linetype') == '--':
            actor.GetProperty().SetLineStipplePattern(65280)
        elif item.getp('linetype') == ':':
            actor.GetProperty().SetLineStipplePattern(0x1111)
            actor.GetProperty().SetLineStippleRepeatFactor(1)
        # actor.GetProperty().SetPointSize(item.getp('pointsize'))
        linewidth = item.getp('linewidth')
        if linewidth:
            actor.GetProperty().SetLineWidth(float(linewidth))

    def _set_actor_material_properties(self, item, actor):
        # set material properties:
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
        x, y = squeeze(item.getp('xdata')), squeeze(item.getp('ydata'))
        z = asarray(item.getp('zdata'))  # scalar field
        try:
            c = item.getp('cdata')       # pseudocolor data
        except KeyError:
            c = z.copy()

        c = z.copy() if c is None else asarray(c)
        assert shape(c) == shape(z)

        if shape(x) != shape(z) and shape(y) != shape(z):
            assert x.ndim == 1 and y.ndim == 1
            x, y = meshgrid(x, y, sparse=False, indexing=item.getp('indexing'))
            # FIXME: use ndgrid instead of meshgrid
        assert shape(x) == shape(z) and shape(y) == shape(z)

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

        points = vtk.vtkPoints()
        points.SetNumberOfPoints(item.getp('numberofpoints'))
        scalars = vtk.vtkFloatArray()
        scalars.SetName('vectors')
        scalars.SetNumberOfTuples(item.getp('numberofpoints'))
        scalars.SetNumberOfComponents(1)
        nx, ny = shape(z)

        if OPTIMIZATION == 'numba':
            pass
        else:
            ind = 0
            for j in range(ny):
                for i in range(nx):
                    points.SetPoint(ind, x[i, j], y[i, j], z[i, j])
                    scalars.SetValue(ind, c[i, j])
                    ind += 1

        sgrid = vtk.vtkStructuredGrid()
        sgrid.SetDimensions(item.getp('dims'))
        sgrid.SetPoints(points)
        sgrid.GetPointData().SetScalars(scalars)

        self.sgrid = vtkAlgorithmSource(sgrid)
        return self.sgrid

    def _create_2D_vector_data(self, item):
        x, y = squeeze(item.getp('xdata')), squeeze(item.getp('ydata'))
        z = item.getp('zdata')           # scalar field
        # vector components:
        u, v = asarray(item.getp('udata')), asarray(item.getp('vdata'))
        w = item.getp('wdata')

        z = zeros(shape(u)) if z is None else squeeze(z)
        w = zeros(shape(u)) if w is None else asarray(w)

        # print(z, w)
        # print(shape(u), shape(w))
        # print(shape(x) == shape(u), shape(y) == shape(u), shape(z) == shape(u), shape(v) == shape(u), shape(w) == shape(u))

        # scale x, y, and z according to data aspect ratio:
        dx, dy, dz = self._ax.getp('daspect')
        x = x / dx; y = y / dy; z = z / dz

        if shape(x) != shape(u) and shape(y) != shape(u):
            assert x.ndim == 1 and y.ndim == 1
            x, y = meshgrid(x, y, sparse=False, indexing=item.getp('indexing'))
            # FIXME: use ndgrid instead of meshgrid
        assert shape(x) == shape(u) and shape(y) == shape(u) and shape(z) == shape(u) and shape(v) == shape(u) and shape(w) == shape(u)

        n = item.getp('numberofpoints')
        points = vtk.vtkPoints()
        points.SetNumberOfPoints(n)
        vectors = vtk.vtkFloatArray()
        vectors.SetName('vectors')
        vectors.SetNumberOfTuples(n)
        vectors.SetNumberOfComponents(3)
        vectors.SetNumberOfValues(3 * n)
        nx, ny = shape(u)

        if OPTIMIZATION == 'numba':
            pass
        else:
            ind = 0
            for j in range(ny):
                for i in range(nx):
                    points.SetPoint(ind, x[i, j], y[i, j], z[i, j])
                    vectors.SetTuple3(ind, u[i, j], v[i, j], w[i, j])
                    ind += 1

        sgrid = vtk.vtkStructuredGrid()
        sgrid.SetDimensions(item.getp('dims'))
        sgrid.SetPoints(points)
        sgrid.GetPointData().SetVectors(vectors)

        self.sgrid = vtkAlgorithmSource(sgrid)
        return self.sgrid

    def _create_3D_scalar_data(self, item):
        x, y, z = squeeze(item.getp('xdata')), squeeze(item.getp('ydata')), squeeze(item.getp('zdata'))
        v = asarray(item.getp('vdata'))  # scalar data
        c = item.getp('cdata')           # pseudocolor data
        # FIXME: What about pseudocolor data?

        if shape(x) != shape(v) and shape(y) != shape(v) and shape(z) != shape(v):
            assert x.ndim == 1 and y.ndim == 1 and z.ndim == 1
            x, y, z = meshgrid(x, y, z, sparse=False, indexing=item.getp('indexing'))
            # FIXME: use ndgrid instead of meshgrid
        assert shape(x) == shape(v) and shape(y) == shape(v) and shape(z) == shape(v)

        # scale x, y, and z according to data aspect ratio:
        dx, dy, dz = self._ax.getp('daspect')
        x, y, z = x / dx, y / dy, z / dz

        points = vtk.vtkPoints()
        points.SetNumberOfPoints(item.getp('numberofpoints'))
        scalars = vtk.vtkFloatArray()
        scalars.SetName('scalars')
        scalars.SetNumberOfTuples(item.getp('numberofpoints'))
        scalars.SetNumberOfComponents(1)
        nx, ny, nz = shape(v)

        if OPTIMIZATION == 'numba':
            pass
        else:
            ind = 0
            for k in range(nz):
                for j in range(ny):
                    for i in range(nx):
                        points.SetPoint(ind, x[i, j, k], y[i, j, k], z[i, j, k])
                        scalars.SetValue(ind, v[i, j, k])
                        ind += 1

        sgrid = vtk.vtkStructuredGrid()
        sgrid.SetDimensions(item.getp('dims'))
        sgrid.SetPoints(points)
        sgrid.GetPointData().SetScalars(scalars)

        self.sgrid = vtkAlgorithmSource(sgrid)
        return self.sgrid

    def _create_3D_vector_data(self, item):
        # grid components
        x, y, z = squeeze(item.getp('xdata')), squeeze(item.getp('ydata')), squeeze(item.getp('zdata'))
        # vector components
        u, v, w = asarray(item.getp('udata')), asarray(item.getp('vdata')), asarray(item.getp('wdata'))

        # scale x, y, and z according to data aspect ratio:
        dx, dy, dz = self._ax.getp('daspect')
        x, y, z = x / dx, y / dy, z / dz

        if shape(x) != shape(u) and shape(y) != shape(u) and shape(z) != shape(u):
            assert x.ndim == 1 and y.ndim == 1 and z.ndim == 1
            x, y, z = meshgrid(x, y, z, sparse=False, indexing=item.getp('indexing'))
            # FIXME: use ndgrid instead of meshgrid
        assert shape(x) == shape(u) and shape(y) == shape(u) and shape(z) == shape(u) and shape(v) == shape(u) and shape(w) == shape(u)

        n = item.getp('numberofpoints')
        points = vtk.vtkPoints()
        points.SetNumberOfPoints(n)
        vectors = vtk.vtkFloatArray()
        vectors.SetName('vectors')
        vectors.SetNumberOfTuples(n)
        vectors.SetNumberOfComponents(3)
        vectors.SetNumberOfValues(3 * n)
        nx, ny, nz = shape(u)
        nc = (nx - 1) * (ny - 1) * (nz - 1)
        scalars = vtk.vtkFloatArray()
        scalars.SetName('scalars')
        scalars.SetNumberOfTuples(nc)
        scalars.SetNumberOfComponents(1)
        scalars.SetNumberOfValues(nc)

        if OPTIMIZATION == 'numba':
            # TODO
            pass
        else:
            ind = 0
            for k in range(nz):
                for j in range(ny):
                    for i in range(nx):
                        points.SetPoint(ind, x[i, j, k], y[i, j, k], z[i, j, k])
                        vectors.SetTuple3(ind, u[i, j, k], v[i, j, k], w[i, j, k])
                        ind += 1

            ind = 0
            for k in range(nz - 1):
                for j in range(ny - 1):
                    for i in range(nx - 1):
                        scalars.SetValue(ind, sqrt(u[i, j, k]**2 + v[i, j, k]**2 + w[i, j, k]**2))
                        ind += 1

        sgrid = vtk.vtkStructuredGrid()
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
            z = zeros(x.shape)

        points = vtk.vtkPoints()
        [points.InsertPoint(_, x[_], y[_], z[_]) for _ in range(len(x))]

        lines = vtk.vtkCellArray()
        lines.InsertNextCell(len(x))

        [lines.InsertCellPoint(_) for _ in range(len(x) - 1)]
        lines.InsertCellPoint(0)

        polydata = vtk.vtkPolyData()
        polydata.SetPoints(points)
        polydata.SetLines(lines)

        sgrid = vtk.vtkStructuredGrid()
        sgrid.SetDimensions(item.getp('dims'))
        sgrid.SetPoints(points)
        self.sgrid = vtkAlgorithmSource(sgrid)

        return vtkAlgorithmSource(polydata, outputType='vtkPolyData')

    def _get_linespecs(self, item):
        '''Return the line marker, line color, line style, and line width of the item'''
        marker = self._markers[item.getp('linemarker')]
        color = self._colors[item.getp('linecolor')]
        style = self._line_styles[item.getp('linetype')]
        width = item.getp('linewidth')
        return marker, color, style, width

    def _add_line(self, item):
        '''Add a 2D or 3D curve to the scene.'''
        print('<line +>') if DEBUG else None

        # get line specifications, TODO: set them in VTK
        marker, color, style, width = self._get_linespecs(item)

        line3D = self._create_3D_line_data(item)

        data = self._cut_data(line3D, item)
        mapper = vtk.vtkDataSetMapper()
        mapper.SetInputConnection(data.GetOutputPort())
        mapper.SetLookupTable(self._ax._colormap)
        cax = self._ax._caxis
        if cax is None:
            data.Update()
            cax = data.GetOutput().GetScalarRange()
        mapper.SetScalarRange(cax)
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        self._set_actor_properties(item, actor)
        self._ax._renderer.AddActor(actor)
        self._ax._apd.AddInputConnection(data.GetOutputPort())

    def _add_surface(self, item, shading='faceted'):
        print('<surface +>') if DEBUG else None

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
        plane = vtk.vtkStructuredGridGeometryFilter()
        plane.SetInputConnection(sgrid.GetOutputPort())
        data = self._cut_data(plane, item)
        normals = vtk.vtkPolyDataNormals()
        normals.SetInputConnection(data.GetOutputPort())
        normals.SetFeatureAngle(45)
        mapper = vtk.vtkDataSetMapper()
        mapper.SetInputConnection(normals.GetOutputPort())
        mapper.SetLookupTable(self._ax._colormap)
        cax = self._ax._caxis
        if cax is None:
            data.Update()
            cax = data.GetOutput().GetScalarRange()
        mapper.SetScalarRange(cax)
        actor = vtk.vtkActor()
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
        print('<contours +>') if DEBUG else None
        sgrid = self._create_2D_scalar_data(item)
        plane = vtk.vtkStructuredGridGeometryFilter()
        plane.SetInputConnection(sgrid.GetOutputPort())
        data = self._cut_data(plane, item)

        filled = item.getp('filled')  # draw filled contour plot if True
        # filled = True  # DEBUG !!
        # print('is filled', filled)
        # print('function', item.getp('function'))
        if filled:
            iso = vtk.vtkBandedPolyDataContourFilter()
            iso.SetScalarModeToValue()
            # iso.SetScalarModeToIndex()
            iso.GenerateContourEdgesOn()
        else:
            iso = vtk.vtkContourFilter()
        iso.SetInputConnection(data.GetOutputPort())

        cvector, clevels = item.getp('cvector'), item.getp('clevels')
        # print('cvector', cvector, 'clevels', clevels) if DEBUG else None
        data.Update(); datao = data.GetOutput()
        if cvector is None:
            # the contour levels are chosen automagically
            zmin, zmax = datao.GetScalarRange()
            iso.SetNumberOfContours(clevels)
            iso.GenerateValues(clevels, zmin, zmax)
        else:
            [iso.SetValue(_, cvector[_]) for _ in range(clevels)]

        isoMapper = vtk.vtkPolyDataMapper()
        isoMapper.SetInputConnection(iso.GetOutputPort())
        cmap = self._ax._colormap
        if filled:
            cmap.SetNumberOfColors(clevels)
            cmap.Build()
        isoMapper.SetLookupTable(cmap)
        cax = self._ax._caxis
        if cax is None:
            cax = datao.GetScalarRange()
        isoMapper.SetScalarRange(cax)
        if item.getp('linecolor'):  # linecolor is defined
            isoMapper.ScalarVisibilityOff()

        isoActor = vtk.vtkActor()
        isoActor.SetMapper(isoMapper)
        self._set_actor_properties(item, isoActor)
        # self.add_legend(item, iso.GetOutput())
        self._ax._renderer.AddActor(isoActor)
        self._ax._apd.AddInputConnection(data.GetOutputPort())

        fgcolor = self._get_color(self._ax.getp('fgcolor'), (0, 0, 0))
        edgecolor = self._get_color(item.getp('edgecolor'), fgcolor)

        if filled:
            # create contour edges:
            edgeMapper = vtk.vtkPolyDataMapper()
            edgeMapper.SetInputData(iso.GetContourEdgesOutput())
            edgeMapper.SetResolveCoincidentTopologyToPolygonOffset()
            edgeActor = vtk.vtkActor()
            edgeActor.SetMapper(edgeMapper)
            edgeActor.GetProperty().SetColor(edgecolor)
            self._ax._renderer.AddActor(edgeActor)

        if item.getp('clabels'):
            # add labels on the contour curves subsample the points and label them
            # print('    adding labels', 'fgcolor', fgcolor, 'edgecolor', edgecolor, 'bgcolor', self._ax.getp('bgcolor'))
            # print('    ratio', int(datao.GetNumberOfPoints() / 50))
            mask = vtk.vtkMaskPoints()
            mask.SetInputConnection(iso.GetOutputPort())
            mask.SetOnRatio(int(datao.GetNumberOfPoints() / 50))
            mask.SetMaximumNumberOfPoints(100)
            mask.RandomModeOn()

            # create labels for points - only show visible points
            visPts = vtk.vtkSelectVisiblePoints()
            visPts.SetInputConnection(mask.GetOutputPort())
            visPts.SetRenderer(self._ax._renderer)
            visPts.Update()  # needed, else data is out of date, see classvtkSelectVisiblePoints.html
            ldm = vtk.vtkLabeledDataMapper()
            ldm.SetInputData(mask.GetOutput())  # vtkLabeledDataMapper has no attribute 'SetInputConnnection'
            ldm.SetLabelFormat('%.1g')
            ldm.SetLabelModeToLabelScalars()
            tprop = ldm.GetLabelTextProperty()
            tprop.SetFontFamilyToArial()
            tprop.SetFontSize(self._ax.getp('fontsize') // 2)
            tprop.SetColor(edgecolor)
            tprop.ShadowOff()
            tprop.BoldOff()
            contourLabels = vtk.vtkActor2D()
            contourLabels.SetMapper(ldm)
            self._ax._renderer.AddActor(contourLabels)

    def _add_vectors(self, item):
        print('<vectors +>') if DEBUG else None

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

        geom = vtk.vtkStructuredGridGeometryFilter()
        geom.SetInputConnection(sgrid.GetOutputPort())
        dataset = self._cut_data(geom, item)
        dataset.Update(); datao = dataset.GetOutput()
        glyph = vtk.vtkGlyph3D()

        if cone_resolution:
            # tip_radius, shaft_radius, tip_length = .1, .03, .35  # default vtk values
            tip_resolution, shaft_resolution = 6, 6
            arrow = vtk.vtkArrowSource()
            # arrow.SetTipLength(tip_length)
            # arrow.SetTipRadius(tip_radius)
            # arrow.SetShaftRadius(shaft_radius)
            arrow.SetTipResolution(cone_resolution * tip_resolution)
            arrow.SetShaftResolution(cone_resolution * shaft_resolution)

        else:
            arrow = vtk.vtkGlyphSource2D()
            arrow.SetGlyphType(marker)
            arrow.SetFilled(item.getp('filledarrows'))
            arrow.SetRotationAngle(rotation)
            if arrow.GetGlyphType() != 9:  # not an arrow
                arrow.DashOn()
                arrow.SetCenter(.75, 0, 0)
            else:
                arrow.SetCenter(.5, 0, 0)
            arrow.SetColor(self._get_color(item.getp('linecolor'), (0, 0, 0)))

        glyph.SetInputConnection(dataset.GetOutputPort())
        glyph.SetSourceConnection(arrow.GetOutputPort())
        glyph.SetColorModeToColorByVector()
        glyph.SetRange(datao.GetScalarRange())
        glyph.ScalingOn()
        glyph.SetScaleModeToScaleByVector()
        glyph.OrientOn()
        glyph.SetVectorModeToUseVector()
        glyph.SetScaleFactor(arrowscale)

        mapper = vtk.vtkPolyDataMapper()
        mapper.ScalarVisibilityOff()
        mapper.SetInputConnection(glyph.GetOutputPort())

        # glyph are costly in terms of rendering, use a LODActor
        LODActor = vtk.vtkLODActor()
        LODActor.SetMapper(mapper)
        self._set_actor_properties(item, LODActor)
        self._ax._renderer.AddActor(LODActor)
        self._ax._apd.AddInputConnection(glyph.GetOutputPort())

    def _add_streams(self, item):
        print('<streams +>') if DEBUG else None

        if item.getp('udata').ndim == 3:
            sgrid = self._create_3D_vector_data(item)
        else:
            sgrid = self._create_2D_vector_data(item)

        # length = sgrid.GetLength()
        # max_velocity = sgrid.GetPointData().GetVectors().GetMaxNorm()
        # max_time = 35. * length / max_velocity

        dx, dy, dz = self._ax.getp('daspect')
        sx = ravel(item.getp('startx')) / dx
        sy = ravel(item.getp('starty')) / dy
        sz = ravel(zeros(sx.shape)) if item.getp('startz') is None else ravel(item.getp('startz')) / dz

        seeds = vtk.vtkProgrammableSource()

        def seeds_pts():
            output = seeds.GetPolyDataOutput()
            points = vtk.vtkPoints()
            verts = vtk.vtkCellArray()
            verts.InsertNextCell(item.getp('numberofstreams'))

            for i in range(item.getp('numberofstreams')):
                verts.InsertCellPoint(points.InsertNextPoint(sx[i], sy[i], sz[i]))

            output.SetPoints(points)
            output.SetVerts(verts)

        seeds.SetExecuteMethod(seeds_pts)
        seeds.Update()

        # The starting point, or the so-called 'seed', of a streamline may be set in two different ways. Starting from global x-y-z 'position' allows you to start a single trace at a specified x-y-z coordinate. If you specify a source object, traces will be generated from each point in the source that is inside the dataset

        streamer = vtk.vtkStreamTracer()

        streamer.SetInputData(sgrid.GetOutput())
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
            streamtube = vtk.vtkTubeFilter()
            streamtube.SetInputConnection(data.GetOutputPort())
            streamtube.SetRadius(radius)
            streamtube.SetNumberOfSides(ncirc)
            streamtube.SetVaryRadiusToVaryRadiusByVector()
            output = streamtube

        elif item.getp('ribbons'):
            width = item.getp('ribbonwidth')
            streamribbon = vtk.vtkRibbonFilter()
            streamribbon.SetInputConnection(data.GetOutputPort())
            streamribbon.VaryWidthOn()
            streamribbon.SetWidthFactor(width)
            # streamribbon.SetAngle(90)
            streamribbon.SetDefaultNormal([0, 1, 0])
            streamribbon.UseDefaultNormalOn()
            output = streamribbon

        else:
            output = data

        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(output.GetOutputPort())
        mapper.SetLookupTable(self._ax._colormap)
        cax = self._ax._caxis

        if cax is None:
            # because of GetInput()
            mapper.Update()
            cax = mapper.GetInput().GetBounds()[4:]
            # cax = sgrid.GetScalarRange()
        mapper.SetScalarRange(cax)
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)

        self._set_shading(item, output, actor)
        self._set_actor_properties(item, actor)
        # self._add_legend(item, output.GetOutputPort())
        self._ax._renderer.AddActor(actor)

        self._ax._apd.AddInputConnection(output.GetOutputPort())

    def _add_isosurface(self, item):
        print('<isosurface +>') if DEBUG else None

        # grid components:
        x, y, z = item.getp('xdata'), item.getp('ydata'), item.getp('zdata')
        v = item.getp('vdata')  # volume
        c = item.getp('cdata')  # pseudocolor data
        isovalue = item.getp('isovalue')

        sgrid = self._create_3D_scalar_data(item)

        iso = vtk.vtkContourFilter()
        iso.SetInputData(sgrid.GetOutput())
        iso.SetValue(0, isovalue)
        data = self._cut_data(iso, item)

        normals = vtk.vtkPolyDataNormals()
        normals.SetInputConnection(data.GetOutputPort())
        normals.SetFeatureAngle(45)

        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(normals.GetOutputPort())
        # mapper.SetScalarModeToUsePointFieldData()
        mapper.SetLookupTable(self._ax._colormap)

        cax = self._ax._caxis
        if cax is None:
            cax = sgrid.GetOutput().GetScalarRange()

        mapper.SetScalarRange(cax)
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        # self._set_shading(item, normals, actor)
        self._set_actor_properties(item, actor)
        self._ax._renderer.AddActor(actor)
        self._ax._apd.AddInputConnection(normals.GetOutputPort())

    def _add_slices(self, item, contours=False):
        print('<slices vol +>') if DEBUG else None

        sgrid = self._create_3D_scalar_data(item)
        # sgrid.Modified()

        sx, sy, sz = item.getp('slices')
        if sz.ndim == 2:
            # sx, sy, and sz defines a surface
            h = Surface(sx, sy, sz)
            sgrid2 = self._create_2D_scalar_data(h)
            plane = vtk.vtkStructuredGridGeometryFilter()
            plane.SetInputConnection(sgrid2.GetOutputPort())
            data = self._cut_data(plane, item)
            data.Update()
            datao = data.GetOutput()
            implds = vtk.vtkImplicitDataSet()
            implds.SetDataSet(datao)
            implds.Modified()
            cut = vtk.vtkCutter()
            cut.SetInputConnection(sgrid.GetOutputPort())
            cut.SetCutFunction(implds)
            cut.GenerateValues(10, -2, 2)
            cut.GenerateCutScalarsOn()
            mapper = vtk.vtkPolyDataMapper()
            mapper.SetInputConnection(cut.GetOutputPort())
            mapper.SetLookupTable(self._ax._colormap)
            cax = self._ax._caxis
            if cax is None:
                cax = datao.GetScalarRange()
            mapper.SetScalarRange(cax)
            actor = vtk.vtkActor()
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
            sgrido = sgrid.GetOutput()
            # print('sgrido', sgrido.GetNumberOfCells(), sgrido.GetNumberOfPoints())
            center = sgrido.GetCenter()
            dx, dy, dz = self._ax.getp('daspect')
            sx, sy, sz = ravel(sx) / dx, ravel(sy) / dy, ravel(sz) / dz
            for i in range(len(sx)):
                normals.append([1, 0, 0])
                origins.append([sx[i], center[1], center[2]])
            for i in range(len(sy)):
                normals.append([0, 1, 0])
                origins.append([center[0], sy[i], center[2]])
            for i in range(len(sz)):
                normals.append([0, 0, 1])
                origins.append([center[0], center[1], sz[i]])
            for i in range(len(normals)):
                plane = vtk.vtkPlane()
                plane.SetOrigin(origins[i])
                plane.SetNormal(normals[i])
                cut = vtk.vtkCutter()
                cut.SetInputData(sgrido)
                cut.SetCutFunction(plane)
                data = self._cut_data(cut, item)
                datao = data.GetOutput()
                # print('datao', datao.GetNumberOfCells(), datao.GetNumberOfPoints())
                mapper = vtk.vtkPolyDataMapper()
                if contours:
                    iso = vtk.vtkContourFilter()
                    iso.SetInputConnection(data.GetOutputPort())
                    cvector = item.getp('cvector')
                    if cvector is not None:
                        for i in range(len(cvector)):
                            iso.SetValue(i, cvector[i])
                    else:
                        zmin, zmax = datao.GetScalarRange()
                        iso.GenerateValues(item.getp('clevels'), zmin, zmax)
                    mapper.SetInputConnection(iso.GetOutputPort())
                else:
                    mapper.SetInputConnection(data.GetOutputPort())
                mapper.SetLookupTable(self._ax._colormap)
                cax = self._ax._caxis
                if cax is None:
                    cax = sgrido.GetScalarRange()
                mapper.SetScalarRange(cax)
                actor = vtk.vtkActor()
                actor.SetMapper(mapper)
                if not contours:
                    self._set_shading(item, data, actor)
                self._set_actor_properties(item, actor)
                self._ax._renderer.AddActor(actor)
                self._ax._apd.AddInputConnection(cut.GetOutputPort())

    def _add_contourslices(self, item):
        print('<contour slice planes +>') if DEBUG else None

        self._add_slices(item, contours=True)

    def _set_figure_size(self, fig):
        print('<figure size>') if DEBUG else None

        width, height = fig.getp('size')
        if width and height:
            # set figure width and height
            self._g.set_size(width, height)
        else:
            # use the default width and height in plotting package
            self._g.set_size(800, 600)
            pass

    def find_poked(self, event):
        '''get the vtkTkRenderWindowIntesractor widget and renderer on which the event has been triggered'''
        # print(dir(event))
        # print(vars(event))
        fig = None
        for fignum, _ in list(self._figs.items()):
            # compare event and find the figure
            if event and id(event.widget) == id(_._g.tkw):
                fig = self.figure(fignum)  # set curfig to this figure
                break

        # to use self._g, we have to have access to the poked figures
        ax = None

        if all(isinstance(_, int) for _ in (event.x, event.y)):
            target = fig._g.iren.FindPokedRenderer(event.x, fig._g.renwin.GetSize()[1] - event.y)
            for _ in fig.getp('axes').values():
                if id(_._renderer) == id(target):
                    # self.axes(_)  # set curax to this axis, this seems to cause the crash
                    fig.setp(curax=_)
                    ax = _
                    break
        if DEBUG:
            pass
            # print('--> poked fig {}'.format(fig.getp('number')), hex(id(fig)), '--> poked ax', hex(id(ax)), 'curax', fig.getp('curax'))
            # print('axes', fig.getp('axes'))

        return fig, ax

    def register_bindings(self, tkw):
        '''we must register the figure bindings in the backend because we have to have access to the backend properties'''
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

        def callback(e, ctrl, shift):
            '''
            stackoverflow.com/a/16082411/5584077
            infohost.nmt.edu/tcc/help/pubs/tkinter/web/key-names.html
            '''
            key = e.keysym.lower()
            print(key, end=' ')
            # print(dir(e))
            # print(vars(e))

            fig, ax = self.find_poked(e)
            if ctrl:
                axs = (ax,)
            elif shift:
                axs = list(fig.getp('axes').values())

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
                    elif key == 's':
                        self.hardcopy('fig.pdf', replot=False, vector_file=True, magnification=1, compression=False)
                        return
                    # got camtarget value from paraview default
                    #  --------- /     ^
                    # |camera-->|      |(view up)   x(focal point) ---> (direction of projection)
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
                        tkw.KeyPressEvent(e, ctrl, shift)
                        return

                # only replot at the end
                self._replot(fig, axs)

        def ctrl_callback(e):
            callback(e, 1, 0)

        def shift_callback(e):
            callback(e, 0, 1)

        tkw.bind('<Control-Key>', ctrl_callback)
        tkw.bind('<Shift-Key>', shift_callback)

        def key_callback(e):
            fig, ax = self.find_poked(e)
            if e.keysym == 'i':
                if getattr(ax, '_iw', None) is not None:
                    fig._g.iren.SetKeyCode('i')
                    # fig._g.iren.CharEvent()
                    # ax._iw.SetInteractor(fig._g.iren)
                    # ax._iw.SetCurrentRenderer(ax._renderer)
                    ax._iw.OnChar()
                    # ax._iw.InvokeEvent('EnableEvent') if not ax._iw._on else ax._iw.InvokeEvent('DisableEvent')
                # self._g.iren.CharEvent()
                # self._g.iren.SetKeySym('i')
                # self._g.iren.KeyPressEvent()
                # tkw.KeyPressEvent(e, 0, 0)
            else:
                # forward the event if not interactive event
                tkw.KeyPressEvent(e, 0, 0)

        tkw.bind('<KeyPress>', key_callback)

    def figure(self, *args, **kwargs):
        # Extension of BaseClass.figure: adding a plotting package figure instance as fig._g and create a link to it as self._g
        fig = BaseClass.figure(self, *args, **kwargs)
        try:
            fig._g
        except:
            # create plotting package figure and save figure instance as fig._g
            self.name = 'Figure ' + str(fig.getp('number'))
            if DEBUG:
                print('creating figure {} in backend'.format(self.name))

            fig._g = _VTKFigure(self, title=self.name)
            self.register_bindings(fig._g.tkw)

        self.fig = fig
        self._g = fig._g  # link for faster access

        return fig

    def closefig(self, backend):
        fig = None
        for _ in list(self._figs.values()):
            _g = getattr(_, '_g', None)
            if id(_g) == id(backend):
                fig = _
                break

        if fig:
            # delete the associated backend !
            for k in list(self._figs):
                if self._figs[k] == fig:
                    del self._figs[k]
            del fig
            if len(self._figs) < 1:
                self._master.quit()

            self.figure(max(self._figs) if len(self._figs) > 0 else None)  # raise another figure

        print('<closefig>') if DEBUG else None

    def _setup_axis(self, ax):
        if DEBUG:
            print('<axis>')
        self._set_limits(ax)
        self._set_daspect(ax)
        self._set_colormap(ax)
        self._set_caxis(ax)

        # create a renderer for this axis and add it to the current figures renderer window
        ax._renderer = vtk.vtkRenderer()
        self._g.renwin.AddRenderer(ax._renderer)

        # Set the renderers background color:
        ax._renderer.SetBackground(*ax.getp('bgcolor'))

        rect = ax.getp('viewport')
        if not rect:
            rect = (0, 0, 1, 1)
        ax._renderer.SetViewport(rect)
        ax._renderer.RemoveAllViewProps()  # clear current scene
        # axshape = self.gcf().getp('axshape')
        # ax._renderer.SetPixelAspect(axshape[1], axshape[0])

        ax._apd = vtk.vtkAppendPolyData()
        if getattr(ax, '_iw', None) is not None:
            if ax._iw._on:  # else iwidget crashes without any information
                ax._iw.Off()

    def _fix_latex(self, legend):
        '''Remove latex syntax a la $, \, {, } etc.'''
        # General fix of latex syntax (more readable)
        legend = legend.strip().replace('**', '^').replace('$', '').replace('{', '').replace('}', '').replace('\\', '')
        # legend = legend.replace('*', '')
        return legend

    def _replot(self, fig=None, axs=()):
        '''Replot all axes and all plotitems in the backend.'''
        # NOTE: only the current figure (gcf) is redrawn.
        print('<replot in backend>') if DEBUG else None
        # reset the plotting package instance in fig._g now if needed

        # if fig:
        #     fig = self.figure(fig.getp('number'))  # make sure sure we have the right figure
        if not fig:
            fig = self.fig
        fig_axes = list(fig.getp('axes').values())

        if axs and all(_ in fig_axes for _ in axs) and len(axs) == len(fig_axes):
            print('--> hard reset')
            fig._g.hard_reset()
            self.register_bindings(fig._g.tkw)
            self._set_figure_size(fig)
        else:
            if False:
                fig._g.hard_reset()
                self.register_bindings(fig._g.tkw)
                self._set_figure_size(fig)
            else:
                fig._g.soft_reset(axs)

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
            self._setup_axis(ax)
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
                    if func == 'isosurface':
                        self._add_isosurface(item)
                    elif func == 'slice_':
                        self._add_slices(item)
                    elif func == 'contourslice':
                        self._add_contourslices(item)
                # legend = self._fix_latex(item.getp('legend'))
                legend = item.getp('legend')
                if legend:
                    # add legend to plot
                    legendActor = vtk.vtkLegendBoxActor()
                    legendActor.SetNumberOfEntries(1)
                    # symbol = vtk.vtkSphereSource(); symbol.Update()  # for an empty symbol, pass an empty vtkPolyData instance
                    legendActor.SetEntry(0, vtk.vtkPolyData(), legend, ax.getp('axiscolor'))
                    legendActor.GetPositionCoordinate().SetCoordinateSystemToNormalizedViewport()
                    legendActor.GetPositionCoordinate().SetValue(0, .8)
                    textProp = legendActor.GetEntryTextProperty()
                    textProp.SetFontSize(textProp.GetFontSize() // 2)
                    if ax.getp('legend_fancybox'):
                        legendActor.BorderOn()
                    ax._renderer.AddActor(legendActor)

            self._set_axis_props(ax)

            if getattr(ax, '_iw', None) is not None:
                print('after reset', ax._iw)
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
                print('<plot data to screen>')
                debug(self, level=0)

        self._g.display(show=self.getp('show'))

    def mainloop(self, **kwargs):
        '''blocking call for showing tk widget'''
        print('<mainloop>') if DEBUG else None
        self.setp(**kwargs)
        self.all_show()
        self._master.mainloop()

    def all_show(self):
        print('<all_show>') if DEBUG else None
        if self.getp('show'):
            for _, fig in list(self._figs.items()):
                self.figure(fig.getp('number'))
                if any(hasattr(ax, '_iw') and ax._iw for _, ax in list(fig.getp('axes').items())):
                    fig._g.tkw.Start()  # self._g.tkw.Initialize()
                    fig._g.tkw.focus_force()
                    fig._g.tkw.update()
                self.show()

    # def all_exit(self):
    #     for _, fig in list(self._figs.items()):
    #         self.figure(fig.getp('number'))
    #         self._g.exit()
    #     self._master.quit()
    #     # self.master.destroy()  # do not destroy, in order to create other figures ...

    def hardcopy(self, filename, **kwargs):
        '''
        Supported extensions in VTK backend:

          * '.ps'  (PostScript)
          * '.eps' (Encapsualted PostScript)
          * '.pdf' (Portable Document Format)
          * '.jpg' (Joint Photographic Experts Group)
          * '.png' (Portable Network Graphics)
          * '.pnm' (Portable Any Map)
          * '.tif' (Tagged Image File Format)
          * '.bmp' (Bitmap Image)

        Optional arguments for JPEG output:

          quality     -- Set the quality of the resulting JPEG image. The
                         argument must be given as an integer between 0 and
                         100, where 100 gives the best quality (but also
                         the largest file). Default quality is 10.

          progressive -- Set whether to use progressive JPEG generation or
                         not. Default is False.

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
        print('--> hardcopy to', filename) if DEBUG else None

        if filename.startswith('.'):
            filename = 'tmp' + filename

        self.setp(**kwargs)

        if not self.getp('show'):  # don't render to screen
            off_ren = self._g.renwin.GetOffScreenRendering()
            self._g.renwin.OffScreenRenderingOn()

        if kwargs.get('replot', True):
            self._replot()

        basename, ext = os.path.splitext(filename)
        if not ext:
            # no extension given, assume .ps:
            ext = '.ps'
            filename += ext

        jpeg_quality = int(kwargs.get('quality', 100))
        progressive = bool(kwargs.get('progressive', False))
        vector_file = bool(kwargs.get('vector_file', False))
        orientation = kwargs.get('orientation', 'portrait')
        raster3d = bool(kwargs.get('raster3d', False))
        compression = bool(kwargs.get('compression', True))
        magnification = int(kwargs.get('magnification', 2))

        if DEBUG:
            for _ in ('jpeg_quality', 'progressive', 'vector_file', 'orientation', 'raster3d', 'compression'):
                print('   ', _, '=', locals()[_])

        landscape = False
        if orientation.lower() == 'landscape':
            landscape = True

        vector_file_formats = {'.ps': 0, '.eps': 1, '.pdf': 2, '.tex': 3}
        if vector_file and ext.lower() in vector_file_formats:
            exp = vtk.vtkGL2PSExporter()
            exp.SetBufferSize(50 * 1024 * 1024)  #  50MB
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

        elif ext.lower() in ('.tif', '.tiff', '.bmp', '.pnm', '.png', '.jpg', '.jpeg', '.ps', '.eps'):
            vtk_image_writers = {
                '.tif': vtk.vtkTIFFWriter(),
                '.tiff': vtk.vtkTIFFWriter(),
                '.bmp': vtk.vtkBMPWriter(),
                '.pnm': vtk.vtkPNMWriter(),
                '.png': vtk.vtkPNGWriter(),
                '.jpg': vtk.vtkJPEGWriter(),
                '.jpeg': vtk.vtkJPEGWriter(),
                '.ps': vtk.vtkPostScriptWriter(),
                '.eps': vtk.vtkPostScriptWriter(),  # gives a normal PS file
            }
            w2if = vtk.vtkWindowToImageFilter()
            w2if.SetMagnification(magnification)
            w2if.SetInput(self._g.renwin)
            if ext.lower() in ('.ps', '.eps'):
                w2if.SetInputBufferTypeToRGB()  # vtkPostScriptWriter only support 1 or 3 (RGB) components not 4 (RGB + alpha)
            else:
                w2if.SetInputBufferTypeToRGBA()  # else all items drawn using alpha channel won't appear
            w2if.ReadFrontBufferOff()  # needed to avoid some desktop overlay on linux
            w2if.Update()  # or w2if.Modified(), advised in documentation
            writer = vtk_image_writers[ext.lower()]
            if ext.lower() in ('.jpg', '.jpeg'):
                writer.SetQuality(jpeg_quality)
                writer.SetProgressive(progressive)
            if ext.lower() in ('.tif', '.tiff'):
                writer.SetCompressionToDeflate()
            writer.SetFileName(filename)
            writer.SetInputConnection(w2if.GetOutputPort())
            writer.Write()
        else:
            msg = 'hardcopy: Extension {} is currently not supported.'.format(ext)
            # raise TypeError(msg)
            print(msg)

        # restore OffScreenRendering state
        if not self.getp('show'):
            self._g.renwin.SetOffScreenRendering(off_ren)

    # reimplement color maps and other methods (if necessary) like clf,
    # closefig, and closefigs here.

    def hsv(self, m=64):
        lut = vtk.vtkLookupTable()
        lut.SetHueRange(0, 1)
        lut.SetSaturationRange(1, 1)
        lut.SetValueRange(1, 1)
        lut.SetNumberOfColors(m)
        lut.Build()
        return lut

    def gray(self, m=64):
        lut = vtk.vtkLookupTable()
        lut.SetHueRange(0, 0)
        lut.SetSaturationRange(0, 0)
        lut.SetValueRange(0, 1)
        lut.SetNumberOfColors(m)
        lut.Build()
        return lut

    def hot(self, m=64):
        lut = vtk.vtkLookupTable()
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
        lut = vtk.vtkLookupTable()
        lut.SetNumberOfColors(m)
        # the last parameter alpha is set to 1 by default  in method declaration
        for i in range(0, m, 4):
            lut.SetTableValue(i, 1, 0, 0, 1)      # red
            lut.SetTableValue(1 + i, 1, 1, 1, 1)  # white
            lut.SetTableValue(2 + i, 0, 0, 1, 1)  # blue
            lut.SetTableValue(3 + i, 0, 0, 0, 1)  # black
        lut.Build()
        return lut

    def jet(self, m=64):
        # blue, cyan, green, yellow, red, black
        lut = vtk.vtkLookupTable()
        lut.SetNumberOfColors(m)
        lut.SetHueRange(.667, 0)
        lut.Build()
        return lut

    def spring(self, m=64):
        lut = vtk.vtkLookupTable()
        lut.SetNumberOfColors(m)
        lut.SetHueRange(0, .17)
        lut.SetSaturationRange(.5, 1)
        lut.SetValueRange(1, 1)
        lut.Build()
        return lut

    def summer(self, m=64):
        lut = vtk.vtkLookupTable()
        lut.SetNumberOfColors(m)
        lut.SetHueRange(.47, .17)
        lut.SetSaturationRange(1, .6)
        lut.SetValueRange(.5, 1)
        lut.Build()
        return lut

    def winter(self, m=64):
        lut = vtk.vtkLookupTable()
        lut.SetNumberOfColors(m)
        lut.SetHueRange(.8, .42)
        lut.SetSaturationRange(1, 1)
        lut.SetValueRange(.6, 1)
        lut.Build()
        return lut

    def autumn(self, m=64):
        lut = vtk.vtkLookupTable()
        lut.SetNumberOfColors(m)
        lut.SetHueRange(0, .15)
        lut.SetSaturationRange(1, 1)
        lut.SetValueRange(1, 1)
        lut.Build()
        return lut

    def viridis(self):
        lut = vtk.vtkLookupTable()
        lut.SetNumberOfTableValues(len(_viridis_data))
        [lut.SetTableValue(i, *_viridis_data[i]) for i in range(len(_viridis_data))]
        return lut

    def magma(self):
        lut = vtk.vtkLookupTable()
        lut.SetNumberOfTableValues(len(_magma_data))
        [lut.SetTableValue(i, *_magma_data[i]) for i in range(len(_magma_data))]
        return lut

    def inferno(self):
        lut = vtk.vtkLookupTable()
        lut.SetNumberOfTableValues(len(_inferno_data))
        [lut.SetTableValue(i, *_inferno_data[i]) for i in range(len(_inferno_data))]
        return lut

    def plasma(self):
        lut = vtk.vtkLookupTable()
        lut.SetNumberOfTableValues(len(_plasma_data))
        [lut.SetTableValue(i, *_plasma_data[i]) for i in range(len(_plasma_data))]
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

# self._g.tkw.bind('<KeyPress-a>', lambda e, s=lineWidget: s.InvokeEvent(vtk.vtkCommand.StartInteractionEvent))

# def foo2(e):
#     print(repr(e.char))
#     self._g.tkw.KeyPressEvent(e, 0, 0)

# self._g.tkw.bind('<KeyPress-u>', foo2)

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

# self._g.tkw.bind('<KeyPress-l>', foo)
# wr = vtk.vtkPolyDataWriter()
# wr.SetInputData(seeds.GetOutput())
# wr.SetFileName('/home/tb246060/Bureau/seeds.vtk')
# wr.Write()


# wr = vtk.vtkStructuredGridWriter()
# wr.SetInputData(sgrid.GetOutput(2))
# wr.SetFileName('/home/tb246060/Bureau/sgrid.vtk')
# wr.Write()


# sgrid = vtk.vtkPointDataToCellData()
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

# rf = vtk.vtkRibbonFilter()
# rf.SetInputConnection(streamer.GetOutputPort())
# rf.SetWidth(.1)
# rf.SetWidthFactor(5)
# streamMapper = vtk.vtkPolyDataMapper()
# streamMapper.SetInputConnection(rf.GetOutputPort())
# streamMapper.SetScalarRange(sgrid.GetOutput().GetScalarRange())
# streamline = vtk.vtkActor()
# streamline.SetMapper(streamMapper)
# streamline.VisibilityOff()

# outline = vtk.vtkStructuredGridOutlineFilter()
# outline.SetInputData(pl3d_output)
# outlineMapper = vtk.vtkPolyDataMapper()
# outlineMapper.SetInputConnection(outline.GetOutputPort())
# outlineActor = vtk.vtkActor()
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
# sgrid = vtk.vtkProgrammableSource()
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
#     camera = vtk.vtkCamera()
#     for _, axis in list(fig.getp('axes').items()):
#         if axis.getp('camera'):
#             if axis.getp('camera').getp('camshare'):
#                 camera = axis.getp('camera').getp('camshare')
#                 break
