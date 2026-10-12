# Thin wrapper over `python3 -m skilldict`. Run `make help`.
PY ?= python3
SD  = $(PY) -m skilldict

.PHONY: help check findings sheets pdf all clean

help:            ## list the targets
	@grep -E '^[a-z]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*## /\t/'

check:           ## CI gate: build, all checks, write dist/ (must end ALL CHECKS PASSED)
	$(SD) check

findings:        ## TC findings report
	$(SD) findings

sheets:          ## score sheets, HTML + rulebook LaTeX -> build/sheets/
	$(SD) sheets

pdf:             ## rulebook sheet next to the generated one, per challenge (needs latexmk)
	$(SD) pdf

all: check sheets pdf   ## everything

clean:           ## remove build/ (dist/ is committed and kept)
	rm -rf build
