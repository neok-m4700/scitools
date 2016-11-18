from scitools.std import *   # for curve plotting


def f(t):
    return t**2 * np.exp(-t**2)

t = np.linspace(0, 3, 31)    # 31 points between 0 and 3
y = np.zeros(len(t), 'd')    # 31 doubles ('d')
for i in range(len(t)):
    y[i] = f(t[i])

plot(t, y)
savefig('plot1a.png')
savefig('plot1a.eps')
show()
