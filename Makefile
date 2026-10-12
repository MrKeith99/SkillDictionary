# Thin wrapper over `python3 -m skilldict`. Run `make help`.
PY ?= python3
SD  = $(PY) -m skilldict

.PHONY: help check findings sheets prices pdf all clean

help:            ## list the targets
	@grep -E '^[a-z]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*## /\t/'

check:           ## CI gate: build every season, all checks, write dist/ (must end ALL CHECKS PASSED)
	$(SD) check

findings:        ## TC findings report for the season in force
	$(SD) findings

sheets:          ## score sheets for every season -> build/<year>/sheets/
	@for y in $$($(SD) seasons | cut -d' ' -f1); do $(SD) sheets $$y; done

prices:          ## reprice with the proposal's pricing rule -> build/<year>/pricing.*
	$(SD) prices

pdf:             ## official vs generated sheets, one PDF per season (needs latexmk)
	@for y in $$($(SD) seasons | cut -d' ' -f1); do $(SD) pdf $$y; done

all: check sheets prices pdf   ## everything

clean:           ## remove build/ (dist/ is committed and kept)
	rm -rf build
