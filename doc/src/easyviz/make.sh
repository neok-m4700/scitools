#!/bin/bash -x
# Create Easyviz documentation.
# clean:
rm -rf tmp_*

# Make .p.py -> .py files and make sure most recent documentation of
# Easyviz is in the __init__.py file:

# Prepare Doconce files and filter them to various formats:
cp easyviz.do.txt tmp_easyviz.do.txt

doconce format html tmp_easyviz.do.txt
doconce format plain tmp_easyviz.do.txt

doconce format latex tmp_easyviz.do.txt --latex_code_style=pyg
scitools subst slice_ 'slice\_' tmp_easyviz.tex   # _ fix
latex -shell-escape tmp_easyviz
latex -shell-escape tmp_easyviz
dvipdf tmp_easyviz.dvi

# note: Unknown target name "slice" will always be reported by rst
# conversion because we write slice_ in the list of Matlab-like commands...

#doconce format gwiki tmp_easyviz.do.txt
#doconce gwiki_figsubst tmp_easyviz.gwiki https://scitools.googlecode.com/hg/doc/easyviz

doconce format sphinx tmp_easyviz.do.txt
doconce sphinx_dir tmp_easyviz
python automake_sphinx.py

#doconce format rst tmp_easyviz.do.txt
#scitools subst '(figs/.+?)\.eps' '\g<1>.png' tmp_easyviz.rst
#rst2html.py tmp_easyviz.rst > tmp_easyviz_rst.html

cp tmp_easyviz.pdf   ../../easyviz/easyviz.pdf
cp tmp_easyviz.html  ../../easyviz/easyviz.html
#cp tmp_easyviz_rst.html  ../../easyviz/easyviz_rst.html
#cp tmp_easyviz.gwiki ../../easyviz/easyviz.gwiki
#cp tmp_easyviz.txt   ../../easyviz/easyviz.txt
preprocess tmp_easyviz.do.txt > tmp.do.txt
cp tmp.do.txt  ../../easyviz/easyviz.do.txt
#cp tmp_easyviz_sphinx.pdf ../../easyviz/easyviz_sphinx.pdf
# must remove old dirs, otherwise new files won't overwrite
rm -rf ../../easyviz/easyviz_sphinx_html
rm -rf ../../easyviz/figs
rm -rf ../../easyviz/easyviz_sphinx_html/figs
cp -r sphinx-rootdir/_build/html ../../easyviz/easyviz_sphinx_html
cp -r figs ../../easyviz/figs  # to make HTML work
#cp -r figs ../../easyviz/easyviz_sphinx_html/figs  # to make Sphinx work
rm -f ../../easyviz/figs/*.*ps # save some diskspace
#cp tmp_easyviz.gwiki ../../../../scitools.wiki/EasyvizDocumentation.wiki

ls ../../easyviz/





