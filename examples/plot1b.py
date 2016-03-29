from scitools.std import *   # for curve plotting

def f(t):
    return t**2*exp(-t**2)

t = linspace(0, 3, 51)    # 51 points between 0 and 3
y = f(t)
plot(t, y, 'r-')

xlabel('t')
ylabel('y')
legend('t^2*exp(-t^2)')
axis([0, 3, -0.05, 0.6])   # t in [0,3], y in [-0.05,0.6]
title('My First Easyviz Demo')
savefig('plot1b.eps')        # save figure to file (PostScript)
savefig('plot1b.png')        # save figure to file (PNG)
input('Press Return key to quit: ')
