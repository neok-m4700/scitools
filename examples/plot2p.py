from scitools.std import *


def f1(t):
    return t**2 * exp(-t**2)


def f2(t):
    return t**2 * f1(t)

t = linspace(0, 3, 51)
y1 = f1(t)
y2 = f2(t)

# Pick out each 4 points and add random noise
t3 = t[::4]      # slice, stride 4
random.seed(11)  # fix random sequence
noise = random.normal(loc=0, scale=0.02, size=len(t3))
y3 = y2[::4] + noise

plot(t, y1, 'r-')
hold('on')
plot(t, y2, 'ks-')
plot(t3, y3, 'bo')

legend('t^2*exp(-t^2)', 't^4*exp(-t^2)', 'data')
title('Simple Plot Demo of t^2*exp(-t^2) and t^4*exp(-t^2) functions')
axis([0, 3, -0.05, 0.6])
xlabel('t')
ylabel('y')
savefig('plot3.eps')
savefig('plot3.png')
show()

