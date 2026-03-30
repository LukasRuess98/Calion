# Minimal Sphinx Makefile
SPHINXBUILD   = sphinx-build
SOURCEDIR     = .
BUILDDIR      = _build

.PHONY: help html clean

help:
	@$(SPHINXBUILD) -M help $(SOURCEDIR) $(BUILDDIR) $(SPHINXOPTS) $(O)

html:
	@$(SPHINXBUILD) -b html $(SOURCEDIR) $(BUILDDIR)/html $(SPHINXOPTS) $(O)
	@echo "Build finished. HTML is in $(BUILDDIR)/html"

clean:
	@rm -rf $(BUILDDIR)
	@echo "Cleaned $(BUILDDIR)"

# Catch-all target for sphinx-build -M
%: Makefile
	@$(SPHINXBUILD) -M $@ $(SOURCEDIR) $(BUILDDIR) $(SPHINXOPTS) $(O)
