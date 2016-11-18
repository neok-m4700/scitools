"""Make plot of a curve in pure text format (ASCII)."""
# this is the same example as in the scitools.aplotter doc string

from scitools.aplotter import plot
import numpy as np
x = np.linspace(-2, 2, 81)
y = np.exp(-.5 * x**2) * np.cos(np.pi * x)
plot(x, y)

plot(x, y, draw_axes=False)

# plot symbols (the dot argument) at data points:
plot(x, y, plot_slope=False)

# drop axis labels:
plot(x, y, plot_labels=False)

plot(x, y, dot='o', plot_slope=False)

# store plot in a string:
p = plot(x, y, output=str)
print(p)
