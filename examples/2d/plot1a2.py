from scitools.std import *   # for curve plotting


def f(t):
    return t**2 * np.exp(-t**2)

t = np.linspace(0, 3, 51)    # 51 points between 0 and 3
y = np.zeros(len(t), 'd')    # 51 doubles ('d')
for i in range(len(t)):
    y[i] = f(t[i])

plot(t, y, 'r-')
savefig('plot1a2.png')
savefig('plot1a2.eps')
show()
