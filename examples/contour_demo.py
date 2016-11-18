#!/usr/bin/env python
vtk = True

if vtk:
    import scitools.globaldata; scitools.globaldata.DEBUG = 1; scitools.globaldata.backend = 'vtk_new'
    from scitools.easyviz import *
    from scitools.std import *
else:
    from scitools.std import *


def fig1():
    # A simple contour plot of the peaks function (standard test function):
    contour(peaks())


def fig2():
    figure()
    # Here we draw 15 red contour lines with double line width:
    xv, yv = ndgrid(np.linspace(-3, 3, 51), np.linspace(-3, 3, 51))
    values = xv * exp(-xv**2 - yv**2)
    contour(xv, yv, values, 15, 'r', linewidth=2)


def fig3():
    figure()
    # Draw contour lines with labels at -2, 0, 2, and 5:
    values = peaks(xv, yv)
    contour(xv, yv, values, [-2, 0, 2, 5])


def fig4():
    figure()
    # Here we combine a contour plot with a quiver plot
    # (note: currently not working with the Gnuplot backend):
    x = y = np.linspace(-2, 2, 21)
    xv, yv = ndgrid(x, y)  # or meshgrid(x, y, indexing='ij')
    values = np.sin(xv) * np.sin(yv) * exp(-xv**2 - xv**2)
    dx, dy = np.gradient(values)
    contour(xv, yv, values, 10, show=False)
    hold('on')
    quiver(xv, yv, dx, dy, 2, show=True)
    hold('off')


def fig5():
    figure()
    # Another example with contour labels:
    x = np.linspace(-2, 2, 201)
    y = np.linspace(-1, 1, 51)
    xv, yv = ndgrid(x, y)
    values = np.sin(3 * yv - xv**2 + 1) + np.cos(2 * yv**2 - 2 * xv)
    contour(xv, yv, values, clabels='on')  # contour(x,y,values,..) also works


def fig6():
    figure()
    # The contourf command draws filled contours:
    values = peaks(201)
    contourf(values, 10, caxis=[-20, 20], title='Filled Contour Plot', savefig='out.pdf')

if __name__ == '__main__':
    funcs = [
        fig1,
        # fig2,
        # fig3,
        # fig4,
        fig5,
        # fig6,
    ]

    [f() for f in funcs]

    show()
    plt.mainloop()
