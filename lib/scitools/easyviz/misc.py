from scitools.numpyutils import seq
from contextlib import contextmanager
import scitools.globaldata
import numpy as np
import os

from functools import cmp_to_key


def _update_from_config_file(d, section='easyviz'):
    'update the dictionary d with values from the config file scitools.cfg'
    import pprint
    for key in d:
        data = scitools.globaldata._config_data.get(section, {})
        if key in data:
            try:
                d[key] = data[key][0]
            except Exception as e:
                raise Exception('%s, trying to set key=%s to % s' % (str(e), key, data[key][0]))


def asiterable(obj):
    'ensure an iterable object (returns a list if not iterable)'
    try:
        if isinstance(obj, str):
            raise
        else:
            iter(obj)
            return obj
    except:
        return [obj]


def _toggle_state(state):
    if state == 'off' or not state:
        return False
    else:
        return True


def _print(*args, **kwargs):
    'print with default verbosity 0'
    lvl = kwargs.pop('lvl', 0)
    dbg = kwargs.pop('dbg', scitools.globaldata.DEBUG)
    kwargs['flush'] = True  # for print calls not ending with '\n'
    if dbg and lvl <= scitools.globaldata.VERBOSE:
        print(*args, **kwargs)


@contextmanager
def _debug(*args, **kwargs):
    'print only if debug and enough verbosity'
    kw = dict(end=' ', lvl=kwargs.pop('lvl', 0), dbg=kwargs.pop('dbg', scitools.globaldata.DEBUG))
    _print('[ ', ' '.join(map(str, args)), sep='', **kw)
    yield
    _print(']', **kw)


@contextmanager
def _msg(*args, **kwargs):
    'always print'
    kw = dict(end=' ', lvl=kwargs.pop('lvl', 0), dbg=kwargs.pop('dbg', True))
    _print('( ', ' '.join(map(str, args)), sep='', **kw)
    yield
    _print(')', **kw)


def _check_type(var, name, type):
    if not isinstance(var, type):
        raise TypeError('variable %s=%s is not of %s' % (name, var, str(type)))
    else:
        return True


def _check_size(a, a_name, expected_size):
    if isinstance(expected_size, int):
        expected_size = (expected_size,)
    # must use np.shape, because of lists
    if np.shape(a) != expected_size:
        raise ValueError('%s has shape %s, expected %s' % (a_name, a.shape, expected_size))


def _check_xyzv(*args, **kwargs):
    nargs = len(args)
    if nargs == 1:
        x, y, z = [None] * 3
        v = np.asarray(args[0])
    elif nargs == 4:
        x, y, z, v = [np.asarray(_) for _ in args]
    else:
        raise ValueError('_check_xyzv: wrong number of arguments')

    try:
        nx, ny, nz = v.shape
    except:
        raise ValueError('_check_xyzv: v must be 3D, not %dD' % len(v.shape))

    indexing = kwargs.get('indexing', 'ij')

    if x is None and y is None and z is None:
        if indexing == 'ij':
            ny, nx = nx, nz  # swap
        x, y, z = np.meshgrid(list(range(ny)),
                              list(range(nx)),
                              list(range(nz)), indexing=indexing)
    else:
        if indexing == 'ij':
            assert (
                x.shape == (nx, ny, nz) or
                x.shape == (nx, 1, 1) or
                x.shape == (nx,)
            ), '_check_xyzv: x has shape %s, expected %s, %s, or %s' % (x.shape, (nx, ny, nz), (nx, 1, 1), (nx,))

            if x.shape == (nx, ny, nz):
                assert y.shape == (nx, ny, nz), '_check_xyzv: x has shape %s, expected y to be %s, not %s' % (x.shape, (nx, ny, nz), y.shape)
                assert z.shape == (nx, ny, nz), '_check_xyzv: x has shape %s, expected z to be %s, not %s' % (x.shape, (nx, ny, nz), z.shape)
            elif x.shape == (nx, 1, 1):
                assert y.shape == (1, ny, 1), '_check_xyzv: x has shape %s, expected y to be %s, not %s' % (x.shape, (1, ny, 1), y.shape)
                assert z.shape == (1, 1, nz), '_check_xyzv: x has shape %s, expected z to be %s, not %s' % (x.shape, (1, 1, nz), z.shape)
            else:  # x.shape == (nx,)
                assert y.shape == (ny,), '_check_xyzv: x has shape %s, expected y to be %s, not %s' % (x.shape, (ny,), y.shape)
                assert z.shape == (nz,), '_check_xyzv: x has shape %s, expected z to be %s, not %s' % (x.shape, (nz,), z.shape)
        else:
            assert (
                x.shape == (nx, ny, nz) or
                x.shape == (1, ny, 1) or
                x.shape == (ny,)
            ), '_check_xyzv: x has shape %s, expected %s, %s, or %s' % (x.shape, (nx, ny, nz), (1, ny, 1), (ny,))

            if x.shape == (nx, ny, nz):
                assert y.shape == (nx, ny, nz), '_check_xyzv: x has shape %s, expected y to be %s, not %s' % (x.shape, (nx, ny, nz), y.shape)
                assert z.shape == (nx, ny, nz), '_check_xyzv: x has shape %s, expected z to be %s, not %s' % (x.shape, (nx, ny, nz), z.shape)
            elif x.shape == (1, ny, 1):
                assert y.shape == (nx, 1, 1), '_check_xyzv: x has shape %s, expected y to be %s, not %s' % (x.shape, (nx, 1, 1), y.shape)
                assert z.shape == (1, 1, nz), '_check_xyzv: x has shape %s, expected z to be %s, not %s' % (x.shape, (1, 1, nz), z.shape)
            else:  # x.shape == (ny,)
                assert y.shape == (nx,), '_check_xyzv: x has shape %s, expected y to be %s, not %s' % (x.shape, (nx,), y.shape)
                assert z.shape == (nz,), '_check_xyzv: x has shape %s, expected z to be %s, not %s' % (x.shape, (nz,), z.shape)

    return x, y, z, v


def _check_xyz(*args, **kwargs):
    nargs = len(args)
    if nargs == 1:
        x, y = [None] * 2
        z = np.asarray(args[0])
    elif nargs == 3:
        x, y, z = [np.asarray(_) for _ in args]
    else:
        raise TypeError('_check_xyz: wrong number of arguments')

    try:
        nx, ny = z.shape
    except:
        raise ValueError('z must be 2D, not %dD' % len(z.shape))

    indexing = kwargs.get('indexing', 'ij')

    if x is None and y is None:
        if indexing == 'ij':
            nx, ny = ny, nx  # swap
        x, y = np.meshgrid(list(range(ny)), list(range(nx)), indexing=indexing)
    else:
        if indexing == 'ij':
            assert (
                x.shape == (nx, ny) or
                x.shape == (nx, 1) or
                len(x) == nx
            ), '_check_xyz: x has shape %s, expected %s, %s, or %s' % (x.shape, (nx, ny), (nx, 1), (nx,))

            assert (
                y.shape == (nx, ny) or
                y.shape == (1, ny) or
                len(y) == ny
            ), '_check_xyz: y has shape %s, expected %s, %s, or %s' % (y.shape, (nx, ny), (1, ny), (ny,))
        else:
            assert (
                x.shape == (nx, ny) or
                x.shape == (1, ny) or
                len(x) == ny
            ), '_check_xyz: x has shape %s, expected %s, %s, or %s' % (x.shape, (nx, ny), (1, ny), (ny,))

            assert (
                y.shape == (nx, ny) or
                y.shape == (nx, 1) or
                len(y) == nx
            ), '_check_xyz: y has shape %s, expected %s, %s, or %s' % (y.shape, (nx, ny), (nx, 1), (nx,))

    return x, y, z


def _check_xyuv(*args, **kwargs):
    nargs = len(args)
    if nargs == 2:
        x, y = [None] * 2
        u, v = [np.asarray(_) for _ in args]
    elif nargs == 4:
        x, y, u, v = [np.asarray(_) for _ in args]
    else:
        raise TypeError('_check_xyuv: wrong number of arguments')

    indexing = kwargs.get('indexing', 'ij')

    us = u.shape
    assert us == v.shape, '_check_xyuv: u and v must be of same shape'

    if len(us) == 1:
        if x is None and y is None:
            x = list(range(us[0]))
            y = list(range(us[0]))
        else:
            assert x.shape == us, '_check_xyuv: x has shape %s, expected %s' % (x.shape, us)
            assert y.shape == us, '_check_xyuv: y has shape %s, expected %s' % (y.shape, us)
    elif len(us) == 2:
        nx, ny = us
        if x is None and y is None:
            if indexing == 'ij':
                x = seq(nx - 1)
                y = seq(ny - 1)
            else:
                x = seq(ny - 1)
                y = seq(nx - 1)
        else:
            if indexing == 'ij':
                assert (
                    x.shape == (nx, ny) or
                    x.shape == (nx, 1) or
                    x.shape == (nx,)
                ), '_check_xyuv: x has shape %s, expected %s, %s, or %s' % (x.shape, (nx, ny), (nx, 1), (nx,))
                assert (
                    y.shape == (nx, ny) or
                    y.shape == (1, ny) or
                    y.shape == (ny,)
                ), '_check_xyuv: y has shape %s, expected %s, %s, or %s' % (y.shape, (nx, ny), (1, ny), (ny,))
            else:
                assert (
                    x.shape == (nx, ny) or
                    x.shape == (1, ny) or
                    x.shape == (ny,)
                ), '_check_xyuv: x has shape %s, expected %s, %s, or %s' % (x.shape, (nx, ny), (1, ny), (ny,))
                assert (
                    y.shape == (nx, ny) or
                    y.shape == (nx, 1) or
                    y.shape == (nx,)
                ), '_check_xyuv: y has shape %s, expected %s, %s, or %s' % (y.shape, (nx, ny), (nx, 1), (nx,))
    else:
        raise ValueError('_check_xyuv: u must be 1D or 2D, not %dD' % len(us))

    return x, y, u, v


def _check_xyzuvw(*args, **kwargs):
    nargs = len(args)
    if nargs == 4:
        x, y = [None] * 2
        z, u, v, w = [np.asarray(_) for _ in args]
    elif nargs == 6:
        x, y, z, u, v, w = [np.asarray(_) for _ in args]
    else:
        raise TypeError('_check_xyzuvw: wrong number of arguments')

    indexing = kwargs.get('indexing', 'xy')

    us = u.shape
    assert us == v.shape == w.shape, \
        '_check_xyzuvw: u, v, and w must be of same shape'

    if len(us) == 1:
        if x is None and y is None:
            x = seq(us[0] - 1)
            y = seq(us[0] - 1)
        else:
            assert x.shape == us, '_check_xyuv: x has shape %s, expected %s' % (x.shape, us)
            assert y.shape == us, '_check_xyuv: y has shape %s, expected %s' % (y.shape, us)
        assert z.shape == us, '_check_xyuv: z has shape %s, expected %s' % (z.shape, us)
    elif len(us) == 2:
        nx, ny = us
        if x is None and y is None:
            x, y, z = _check_xyz(z, indexing=indexing)
        else:
            x, y, z = _check_xyz(x, y, z, indexing=indexing)
        assert z.shape == us, '_check_xyzuvw: z, u, v, and w must be of same shape'
    elif len(us) == 3:
        nx, ny, nz = us
        if x is None and y is None:
            if indexing == 'ij':
                nx, ny = ny, nx  # swap
            x, y, junk = np.meshgrid(seq(ny - 1), seq(nx - 1), seq(nz - 1))
        else:
            if indexing == 'ij':
                assert (
                    x.shape == us or
                    x.shape == (nx, 1, 1) or
                    x.shape == (nx,)
                ), '_check_xyzuvw: x has shape %s, expected %s, %s, or %s' % (x.shape, us, (nx, 1, 1), (nx,))
                assert (
                    y.shape == us or
                    y.shape == (1, ny, 1) or
                    y.shape == (ny,)
                ), '_check_xyzuvw: y has shape %s, expected %s, %s, or %s' % (y.shape, us, (1, ny, 1), (ny,))
            else:
                assert (
                    x.shape == us or
                    x.shape == (1, ny, 1) or
                    x.shape == (ny,)
                ), '_check_xyzuvw: x has shape %s, expected %s, %s, or %s' % (x.shape, us, (1, ny, 1), (ny,))
                assert (
                    y.shape == us or
                    y.shape == (nx, 1, 1) or
                    y.shape == (nx,)
                ), '_check_xyzuvw: y has shape %s, expected %s, %s, or %s' % (y.shape, us, (nx, 1, 1), (nx,))
        assert (
            z.shape == us or
            z.shape == (1, 1, nz) or
            z.shape == (nz,)
        ), '_check_xyzuvw: z has shape %s, expected %s, %s, or %s' % (z.shape, us, (1, 1, nz), (nz,))
    else:
        raise ValueError('_check_xyzuvw: u must be 1D, 2D, or 3D, not %dD' % len(us))

    return x, y, z, u, v, w


# @cmp_to_key
# def _cmpPlotProperties(a, b):

#     '''Sort cmp-function for PlotProperties'''
#     plotorder = [Volume, Streams, Surface, Contours,
#                  VelocityVectors, Bars, Line]
#     assert isinstance(a, PlotProperties)
#     assert isinstance(b, PlotProperties)
#     assert len(PlotProperties.__class__.__subclasses__(PlotProperties)) == \
# len(plotorder)  # Check all subclasses is in plotorder
#     return cmp(plotorder.index(a.__class__), plotorder.index(b.__class__))


def _cmpPlotProperties(self, item):
    plotorder = [Volume, Streams, Surface, Contours, VelocityVectors, Bars, Line]
    assert isinstance(item, PlotProperties)
    assert len(PlotProperties.__class__.__subclasses__(PlotProperties)) == len(plotorder)  # check all subclasses is in plotorder
    return plotorder.index(item.__class__)
