#!/usr/bin/env python
import glob
import sys
import subprocess as sp

demos = glob.glob('*.py')
avoid = ('runall.py', 'demo_pyreport.py', 'grab_backend_demo.py')
for filename in avoid:
    demos.remove(filename)

from scitools.std import backend
try:
    backend = sys.argv[1]
except IndexError:
    pass

for filename in sorted(demos):
    backend_old = backend
    answer = input(filename + '? ')
    if answer.lower() == 'n':
        continue
    if 'matlab' in filename and not backend.startswith('matlab'):
        continue
    if 'isosurf' in filename or 'streamtube' in filename or 'slice' in filename or 'contourslice' in filename:
        backend_old = backend
        backend = 'vtk_new'

    cmd = ['python', filename, '--SCITOOLS_easyviz_backend', backend]
    sp.check_call(cmd)
    backend = backend_old  # restore backend

# surf_demo2
