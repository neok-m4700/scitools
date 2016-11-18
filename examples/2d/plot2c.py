from scitools.std import *


def f1(t):
    return t**2 * np.exp(-t**2)


def f2(t):
    return t**2 * f1(t)

t = np.linspace(0, 3, 51)
y1 = f1(t)
y2 = f2(t)

# Matlab-style syntax:
plot(t, y1, 'r-')
hold('on')
plot(t, y2, 'bo')

xlabel('t')
ylabel('y')
legend('t^2*exp(-t^2)', 't^4*exp(-t^2)')
title('Plotting two curves in the same plot')
savefig('plot2c.eps')
savefig('plot2c.png')
