#!/usr/bin/env bash

# no linkage
# conda inspect linkages $PKG_NAME

# (set -o posix; set)

# NOTE: we have to extend the PYTHONPATH for the vtk libraries
# WARNING: we have to change SP_DIR, since it points to the build env and we are now in the test env
SP_DIR=$(python -c 'import site; print(site.getsitepackages()[0])')

# still the nvidia iglx problem, with vtk
PYTHONPATH=$SP_DIR/vtk:$PYTHONPATH python tester.py || true
