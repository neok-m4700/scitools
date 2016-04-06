#!/usr/bin/env python

import scitools.globaldata; scitools.globaldata.DEBUG = 1
from scitools.easyviz import *
from scitools.easyviz.vtk_new_ import *
from numpy import pi

setp(interactive=False)

t = linspace(0, 10 * pi, 201)
plot3(sin(t), cos(t), t, title='A Helix')
savefig('tmp1.eps')
savefig('tmp1.png')
show()

figure()
t = linspace(-5, 5, 501)
x, y, z = (2 + t**2) * sin(10 * t), (2 + t**2) * cos(10 * t), t

plot3(x, y, z)
grid('on')
xlabel('x(t)')
ylabel('y(t)')
zlabel('z(t)')
title('plot3 example')
savefig('tmp2.eps')
savefig('tmp2.png')
show()

figure()
t = linspace(0, 15 * pi, 301)
x, y, z = exp(-t / 10) * cos(t),  exp(-t / 10) * sin(t), t

subplot(221); plot3(x, y, z)
subplot(222); plot3(x, y, z, view=2)
subplot(223); plot3(x, y, z, view=[90, 90])
subplot(224); plot3(x, y, z, view=[90, 0])
show()

input('Press Return key to quit: ')
