#!/usr/bin/env python

'Examples taken from fill_demo.py and fill_demo2.py in Matplotlib'

from scitools.std import *

t = np.linspace(0.0, 1.0, 101)
s = np.sin(2 * 2 * pi * t)

fill(t, s * np.exp(-5 * t), 'r', grid=True)

figure()
t = np.linspace(0.0, 3.0, 301)
s = np.sin(2 * pi * t)
c = np.sin(4 * pi * t)
fill(t, s, 'b', t, c, 'g', opacity=0.2)

legend('domain1', 'domain2')
clf()

plot(t, s, legend='a')
plot(t, s + 2, legend='b')
