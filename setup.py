#!/usr/bin/env python
import os
import sys

from distutils.core import setup

# Make sure we import from the source code in lib/scitools, not an installed scitools package
sys.path.insert(0, os.path.join('lib'))
import scitools

setup(version=str(scitools.version),
      author=', '.join(scitools.author),
      author_email="<hpl@simula.no>",
      description=scitools.__doc__,
      license="BSD",
      name="SciTools",
      url="http://scitools.googlecode.com",
      package_dir={'': 'lib'},
      packages=['scitools', os.path.join("scitools", "easyviz"), ],
      package_data={'': ['scitools.cfg']},
      )
