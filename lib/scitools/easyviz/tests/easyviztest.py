import unittest
import time

from scitools.numpyutils import *
from scitools.easyviz import *

import random

hardcopy_counter = 0
psplot = False
prompt = ''
if backend == 'gnuplot':
    pause = 0.2
else:
    pause = 0.0
clear_figure = False
new_figure = True
screenplot = True
setp(show=screenplot)


def next(clear_figure=False, prompt='', pause=0,
         save_hardcopy=False, new_figure=False):
    if save_hardcopy:
        global hardcopy_counter
        hardcopy('tmp_easyviz_plot%03d.eps' % hardcopy_counter, color=True)
        hardcopy_counter += 1
    if prompt:
        input(prompt)
    if pause:
        time.sleep(pause)
    if clear_figure:
        clf()
    if new_figure:
        figure()

n = lambda: next(clear_figure, prompt, pause, psplot, new_figure)


class EasyvizTestCase(unittest.TestCase):

    def get_line_data(self, n=41):
        x = np.linspace(0, 15, n)
        y = np.sin(x) * x
        v = np.sin(x) * np.sqrt(x)
        w = np.sin(x) * x**0.33333333
        return x, y, v, w

    def get_3D_line_data(self, n=41):
        t = np.linspace(0, 2 * pi, 40)
        x = np.sin(t)
        y = np.cos(t)
        return x, y, t

    def get_format_string_data(self):
        colors = Line._colors
        try:
            colors.remove('w')  # remove white
        except:
            pass
        markers = Line._markers
        linestyles = Line._linestyles
        format = []
        for marker in markers:
            format.append(''.join([random.choice(colors), marker,
                                   random.choice(linestyles)]))
        return format

    def get_2D_data(self, n=21, sparse=True, indexing='ij'):
        x = y = np.linspace(-3, 3, n)
        xv, yv = np.meshgrid(x, y, sparse=sparse, indexing=indexing)
        values = peaks(xv, yv)
        return x, y, xv, yv, values

    def get_3D_data(self, sparse=True, indexing='ij'):
        x = y = z = np.linspace(-3, 3, 13)
        xv, yv, zv = np.meshgrid(x, y, z, sparse=sparse, indexing=indexing)
        values = xv**np.exp(-xv**2 - yv**2 - zv**2)
        return x, y, z, xv, yv, zv, values

    def get_2D_vector_data(self, n=13, sparse=True, indexing='ij'):
        x = y = np.linspace(-2, 2, n)
        xv, yv = np.meshgrid(x, y, sparse=sparse, indexing=indexing)
        values = xv * np.exp(-xv**2 - yv**2)
        uv, vv = np.gradient(values)
        return x, y, xv, yv, values, uv, vv

    def get_3D_vector_data(self, sparse=True, indexing='ij'):
        x = y = z = np.linspace(-3, 3, 13)
        xv, yv, zv = np.meshgrid(x, y, z, sparse=sparse, indexing=indexing)
        values = xv**np.exp(-xv**2 - yv**2 - zv**2)

        return x, y, z, xv, yv, zv, values
